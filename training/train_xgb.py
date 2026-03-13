"""XGBoost model training with bounded hyperparameter search."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import randint, uniform
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV

from config.settings import settings
from models.registry import save as save_model
from utils.logging import log

REPORTS_DIR = Path("reports")


def train_xgb(
    X_train: pd.DataFrame | np.ndarray[Any, np.dtype[Any]],
    y_train: pd.Series | np.ndarray[Any, np.dtype[Any]],
    X_val: pd.DataFrame | np.ndarray[Any, np.dtype[Any]],
    y_val: pd.Series | np.ndarray[Any, np.dtype[Any]],
    *,
    n_iter: int = 25,
    cv: int = 3,
    artifact_name: str = "xgb_model",
) -> dict[str, Any]:
    """Train an XGBoost classifier with randomised hyperparameter search.

    Handles class imbalance via ``scale_pos_weight``.  Persists the best
    model to ``models/artifacts/`` and writes validation metrics +
    best params to ``reports/xgb_metrics.json``.

    Args:
        X_train: Training feature matrix.
        y_train: Binary labels (0 = performing, 1 = default/delinquent).
        X_val:   Held-out validation features.
        y_val:   Held-out validation labels.
        n_iter:  Number of random hyperparameter combinations to evaluate.
        cv:      Inner cross-validation folds for the search.
        artifact_name: Joblib artifact filename (without extension).

    Returns:
        Dict with keys ``model``, ``best_params``, and ``metrics``.
    """
    from xgboost import XGBClassifier  # lazy — not in stdlib; installed via pyproject.toml

    log.info("Starting XGBoost training — n_iter={}, cv={}", n_iter, cv)

    y_train_arr = np.asarray(y_train)
    n_neg = int(np.sum(y_train_arr == 0))
    n_pos = int(np.sum(y_train_arr == 1))
    scale_pos_weight = float(n_neg / max(n_pos, 1))
    log.info(
        "Class balance  neg={} pos={}  scale_pos_weight={:.2f}", n_neg, n_pos, scale_pos_weight
    )

    base = XGBClassifier(
        objective="binary:logistic",
        eval_metric="auc",
        scale_pos_weight=scale_pos_weight,
        random_state=settings.random_seed,
        n_jobs=-1,
        tree_method="hist",
        verbosity=0,
    )

    # Bounded search space — keeps wall-clock time predictable
    param_dist: dict[str, Any] = {
        "n_estimators": randint(100, 601),  # [100, 600]
        "max_depth": randint(3, 10),  # [3, 9]
        "learning_rate": uniform(0.01, 0.29),  # [0.01, 0.30]
        "subsample": uniform(0.6, 0.4),  # [0.6, 1.0]
        "colsample_bytree": uniform(0.5, 0.5),  # [0.5, 1.0]
        "min_child_weight": randint(1, 11),  # [1, 10]
        "reg_alpha": uniform(0.0, 1.0),  # L1
        "reg_lambda": uniform(0.5, 4.5),  # L2 [0.5, 5.0]
    }

    search = RandomizedSearchCV(
        base,
        param_distributions=param_dist,
        n_iter=n_iter,
        scoring="roc_auc",
        cv=cv,
        refit=True,
        verbose=1,
        random_state=settings.random_seed,
        n_jobs=-1,
    )
    search.fit(X_train, y_train_arr)

    model = search.best_estimator_
    log.info("Best CV ROC-AUC={:.4f}  params={}", search.best_score_, search.best_params_)

    # ── Validation metrics ────────────────────────────────────────────────
    y_val_arr = np.asarray(y_val)
    y_prob = model.predict_proba(X_val)[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)

    metrics: dict[str, float] = {
        "roc_auc": float(roc_auc_score(y_val_arr, y_prob)),
        "avg_precision": float(average_precision_score(y_val_arr, y_prob)),
        "brier_score": float(brier_score_loss(y_val_arr, y_prob)),
        "log_loss": float(log_loss(y_val_arr, y_prob)),
        "accuracy": float(np.mean(y_pred == y_val_arr)),
        "cv_roc_auc": float(search.best_score_),
    }
    log.info("Validation metrics: {}", metrics)

    # ── Persist ───────────────────────────────────────────────────────────
    save_model(model, artifact_name)
    _write_metrics(metrics, dict(search.best_params_))

    return {"model": model, "best_params": dict(search.best_params_), "metrics": metrics}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _write_metrics(metrics: dict[str, float], best_params: dict[str, Any]) -> None:
    """Serialise metrics and best params to reports/xgb_metrics.json."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"metrics": metrics, "best_params": best_params}
    out = REPORTS_DIR / "xgb_metrics.json"
    out.write_text(json.dumps(payload, indent=2, default=str))
    log.info("Metrics written to {}", out)
