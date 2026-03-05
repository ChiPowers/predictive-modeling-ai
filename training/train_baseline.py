"""Baseline logistic-regression trainer.

Usage (CLI)::

    python -m training.train_baseline \
        --features-path data/features/features.parquet \
        --config-path config/training.yaml

Or from Python::

    from training.train_baseline import run
    run("data/features/features.parquet", "config/training.yaml")
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from models.registry import save
from training.split import split_by_time
from utils.logging import log

REPORTS_DIR = Path(__file__).parent.parent / "reports"


def _load_config(config_path: str | Path) -> dict[str, Any]:
    with open(config_path) as fh:
        return yaml.safe_load(fh)


def _load_features(features_path: str | Path) -> pd.DataFrame:
    path = Path(features_path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _evaluate(
    model: Pipeline,
    X: pd.DataFrame,
    y: pd.Series,
    split_name: str,
) -> dict[str, float]:
    proba = model.predict_proba(X)[:, 1]
    auc = float(roc_auc_score(y, proba))
    ap = float(average_precision_score(y, proba))
    brier = float(brier_score_loss(y, proba))

    precision, recall, thresholds = precision_recall_curve(y, proba)
    # F1 at each threshold; pick the best
    f1_scores = np.where(
        (precision + recall) == 0,
        0.0,
        2 * precision * recall / (precision + recall),
    )
    best_idx = int(np.argmax(f1_scores))
    best_threshold = float(thresholds[best_idx]) if len(thresholds) > best_idx else 0.5
    best_f1 = float(f1_scores[best_idx])
    best_precision = float(precision[best_idx])
    best_recall = float(recall[best_idx])

    metrics = {
        "auc_roc": auc,
        "average_precision": ap,
        "brier_score": brier,
        "best_f1": best_f1,
        "best_precision": best_precision,
        "best_recall": best_recall,
        "best_threshold": best_threshold,
        "n_samples": len(y),
        "positive_rate": float(y.mean()),
    }

    log.info(
        "{} — AUC-ROC: {:.4f}  AP: {:.4f}  Brier: {:.4f}  F1@best: {:.4f}",
        split_name,
        auc,
        ap,
        brier,
        best_f1,
    )
    return metrics


def run(features_path: str | Path, config_path: str | Path) -> dict[str, Any]:
    """Train baseline and return a metrics dict keyed by split name."""
    cfg = _load_config(config_path)
    training_cfg = cfg["training"]

    date_col: str = training_cfg["date_col"]
    target_col: str = training_cfg["target_col"]
    feature_cols: list[str] = training_cfg["feature_cols"]
    train_ratio: float = training_cfg["split"]["train_ratio"]
    val_ratio: float = training_cfg["split"]["val_ratio"]
    test_ratio: float = training_cfg["split"]["test_ratio"]
    model_name: str = training_cfg.get("model_name", "baseline_logreg")

    lr_params: dict[str, Any] = training_cfg.get(
        "logistic_regression",
        {"C": 1.0, "max_iter": 1000, "solver": "lbfgs", "random_state": 42},
    )

    log.info("Loading features from {}", features_path)
    df = _load_features(features_path)

    split = split_by_time(df, date_col, train_ratio, val_ratio, test_ratio)

    X_train = split.train[feature_cols]
    y_train = split.train[target_col]
    X_val = split.val[feature_cols]
    y_val = split.val[target_col]
    X_test = split.test[feature_cols]
    y_test = split.test[target_col]

    log.info("Training logistic regression …")
    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(**lr_params)),
        ]
    )
    pipeline.fit(X_train, y_train)

    metrics: dict[str, Any] = {
        "model": model_name,
        "split_boundaries": {
            "train_end": str(split.train_end),
            "val_end": str(split.val_end),
            "test_end": str(split.test_end),
        },
        "train": _evaluate(pipeline, X_train, y_train, "train"),
        "val": _evaluate(pipeline, X_val, y_val, "val"),
        "test": _evaluate(pipeline, X_test, y_test, "test"),
    }

    # Save model artifact
    artifact_path = save(pipeline, model_name)
    metrics["artifact_path"] = str(artifact_path)
    log.info("Model saved to {}", artifact_path)

    # Save metrics report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "baseline_metrics.json"
    with open(report_path, "w") as fh:
        json.dump(metrics, fh, indent=2)
    log.info("Metrics saved to {}", report_path)

    return metrics


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train baseline logistic regression")
    parser.add_argument(
        "--features-path",
        required=True,
        help="Path to features file (.parquet or .csv)",
    )
    parser.add_argument(
        "--config-path",
        default="config/training.yaml",
        help="Path to training config YAML",
    )
    args = parser.parse_args()
    run(args.features_path, args.config_path)
