"""Model training orchestration.

Supported model keys
--------------------
``prophet``
    Fits a Facebook Prophet model on aggregate monthly delinquency rates
    derived from the Fannie Mae performance parquet.  Outputs a trend
    forecast that the service ``/forecast`` endpoint can serve.

``sklearn-logreg``
    Logistic regression PD (probability-of-default) classifier trained on
    the origination feature parquet.  Fast and interpretable baseline.

``sklearn-rf``
    Random Forest PD classifier.  Typically higher AUC than logreg at
    the cost of interpretability.

Usage
-----
    from training.trainer import train_model

    train_model("prophet")
    train_model("sklearn-logreg")
    train_model("sklearn-rf")
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import roc_auc_score, classification_report

import yaml

from config.settings import settings
from models.registry import save as save_model
from utils.logging import log

_DATA_PATHS = Path(__file__).resolve().parents[1] / "config" / "data_paths.yaml"

# ---------------------------------------------------------------------------
# Feature columns used for PD modelling (subset of origination features)
# ---------------------------------------------------------------------------

_PD_FEATURE_COLS: list[str] = [
    "credit_score",
    "orig_ltv",
    "orig_cltv",
    "orig_dti",
    "orig_upb",
    "orig_interest_rate",
    "orig_loan_term",
    "num_units",
    "num_borrowers",
    "log_upb",
    "is_first_time_homebuyer",
    "is_high_ltv",
    "is_high_dti",
    "is_arm",
    "is_jumbo",
    "occupancy_code",
    "loan_purpose_code",
    "channel_code",
    "property_type_code",
]

# Default label column — 1 if the loan ever became 90+ DPD, 0 otherwise
_LABEL_COL = "default_flag"

# Prophet output columns used by the service
PROPHET_FORECAST_COLS = ["ds", "yhat", "yhat_lower", "yhat_upper"]


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------


def train_model(model: str) -> Path:
    """Train a model and persist its artifact.

    Args:
        model: Model identifier key.

    Returns:
        Path to the saved artifact.

    Raises:
        ValueError: If ``model`` is not a recognised key.
        FileNotFoundError: If required processed data is not found.
    """
    log.info("train_model called for model={}", model)

    if model == "prophet":
        return _train_prophet()
    if model == "sklearn-logreg":
        return _train_sklearn(model_key="sklearn-logreg", use_rf=False)
    if model == "sklearn-rf":
        return _train_sklearn(model_key="sklearn-rf", use_rf=True)

    raise ValueError(
        f"Unknown model key '{model}'. "
        "Supported: 'prophet', 'sklearn-logreg', 'sklearn-rf'"
    )


# ---------------------------------------------------------------------------
# Prophet — aggregate delinquency-rate trend forecast
# ---------------------------------------------------------------------------


def _load_performance_parquet() -> pd.DataFrame:
    with open(_DATA_PATHS) as fh:
        cfg = yaml.safe_load(fh)["fannie_mae"]
    perf_dir = Path(cfg["processed_dir"]) / "performance"
    paths = sorted(perf_dir.glob("*.parquet"))
    if not paths:
        raise FileNotFoundError(
            f"No performance parquet files in {perf_dir}. "
            "Run `pmai ingest --source fannie-mae` first."
        )
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)


def _build_delinquency_ts(perf_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate monthly delinquency rate from performance data.

    Returns a DataFrame with columns ``ds`` (datetime) and ``y`` (rate 0–1).
    """
    perf = perf_df.copy()
    perf["period"] = pd.to_numeric(perf["monthly_reporting_period"], errors="coerce")
    perf = perf.dropna(subset=["period"]).copy()
    perf["period"] = perf["period"].astype(int).astype(str)
    # Convert YYYYMM → datetime
    perf["ds"] = pd.to_datetime(perf["period"], format="%Y%m", errors="coerce")
    perf = perf.dropna(subset=["ds"])

    status = pd.to_numeric(perf["current_delinquency_status"], errors="coerce").fillna(0)
    perf["is_delinquent"] = (status > 0).astype(int)

    ts = (
        perf.groupby("ds")
        .agg(n_loans=("is_delinquent", "count"), n_delinquent=("is_delinquent", "sum"))
        .reset_index()
    )
    ts["y"] = (ts["n_delinquent"] / ts["n_loans"].clip(lower=1)).clip(0, 1)
    return ts[["ds", "y"]].sort_values("ds")


def _train_prophet() -> Path:
    """Fit Prophet on aggregate monthly delinquency rate and save artifact."""
    from prophet import Prophet  # import here to keep training import lightweight

    log.info("Loading performance data for Prophet training...")
    perf_df = _load_performance_parquet()
    ts = _build_delinquency_ts(perf_df)
    log.info("Time series built: {} monthly observations", len(ts))

    if len(ts) < 2:
        raise ValueError(
            f"Need at least 2 monthly observations to fit Prophet, got {len(ts)}. "
            "Ingest more performance quarters."
        )

    m = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10.0,
    )
    m.fit(ts)

    # Quick in-sample diagnostic
    future = m.make_future_dataframe(periods=settings.forecast_horizon, freq="MS")
    forecast = m.predict(future)
    in_sample = forecast[forecast["ds"].isin(ts["ds"])]
    actual = ts.set_index("ds")["y"]
    predicted = in_sample.set_index("ds")["yhat"]
    aligned = actual.align(predicted, join="inner")
    mae = float((aligned[0] - aligned[1]).abs().mean())
    log.info("Prophet in-sample MAE: {:.4f}", mae)

    artifact_path = save_model(m, "prophet")
    log.info("Prophet model saved → {}", artifact_path)
    return artifact_path


# ---------------------------------------------------------------------------
# Sklearn — loan-level PD classification
# ---------------------------------------------------------------------------


def _load_feature_parquet() -> pd.DataFrame:
    with open(_DATA_PATHS) as fh:
        cfg = yaml.safe_load(fh)["fannie_mae"]
    feat_path = Path(cfg["processed_dir"]) / "features" / "features.parquet"
    if not feat_path.exists():
        raise FileNotFoundError(
            f"Feature parquet not found at {feat_path}. "
            "Run `pmai features --source fannie-mae` first."
        )
    return pd.read_parquet(feat_path)


def _make_default_label(df: pd.DataFrame) -> pd.Series:
    """Derive a binary default label from available columns.

    Uses ``max_dpd`` (peak days-past-due computed during feature engineering)
    when available; falls back to the ``zero_balance_code`` column.
    """
    if "max_dpd" in df.columns:
        return (pd.to_numeric(df["max_dpd"], errors="coerce").fillna(0) >= 3).astype(int)
    if "zero_balance_code" in df.columns:
        # Zero balance codes 02/03/06/09/15 indicate foreclosure / short sale / REO
        default_codes = {"02", "03", "06", "09", "15"}
        return df["zero_balance_code"].astype(str).isin(default_codes).astype(int)
    # No label signal — fabricate a synthetic label for demonstration
    log.warning(
        "No default label column found. Using synthetic 5%% default rate for demonstration."
    )
    rng = np.random.default_rng(settings.random_seed)
    return pd.Series(rng.binomial(1, 0.05, len(df)), index=df.index)


def _build_pd_pipeline(use_rf: bool) -> Pipeline:
    imputer = SimpleImputer(strategy="median")
    if use_rf:
        clf = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            min_samples_leaf=50,
            class_weight="balanced",
            random_state=settings.random_seed,
            n_jobs=-1,
        )
        return Pipeline([("imputer", imputer), ("clf", clf)])
    else:
        clf = LogisticRegression(
            max_iter=500,
            class_weight="balanced",
            random_state=settings.random_seed,
            C=0.1,
        )
        return Pipeline([("imputer", imputer), ("scaler", StandardScaler()), ("clf", clf)])


def _train_sklearn(model_key: str, use_rf: bool) -> Path:
    """Fit a sklearn PD classifier and save the pipeline artifact."""
    log.info("Loading feature parquet for {} training...", model_key)
    feat_df = _load_feature_parquet()

    # Select feature columns that are present
    feature_cols = [c for c in _PD_FEATURE_COLS if c in feat_df.columns]
    if not feature_cols:
        raise ValueError(
            f"None of the expected feature columns {_PD_FEATURE_COLS} are present. "
            "Run `pmai features --source fannie-mae` first."
        )
    log.info("Using {} feature columns for {}", len(feature_cols), model_key)

    X = feat_df[feature_cols].copy()
    y = _make_default_label(feat_df)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=settings.test_split,
        random_state=settings.random_seed,
        stratify=y,
    )
    log.info(
        "Train/test split: {:,} train / {:,} test (default rate: train={:.2%} test={:.2%})",
        len(X_train), len(X_test),
        y_train.mean(), y_test.mean(),
    )

    pipeline = _build_pd_pipeline(use_rf)
    pipeline.fit(X_train, y_train)

    y_pred_proba = pipeline.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, y_pred_proba))
    log.info("{} test AUC: {:.4f}", model_key, auc)

    y_pred = (y_pred_proba >= 0.5).astype(int)
    report = classification_report(y_test, y_pred, output_dict=False)
    log.info("Classification report:\n{}", report)

    # Attach evaluation metadata so the registry can surface it
    artifact: dict[str, Any] = {
        "pipeline": pipeline,
        "feature_cols": feature_cols,
        "metrics": {"auc": auc},
        "model_key": model_key,
    }

    path = save_model(artifact, model_key)
    log.info("{} model saved → {} (AUC={:.4f})", model_key, path, auc)
    return path
