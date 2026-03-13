"""Model training orchestration with MLflow tracking.

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
    train_model("sklearn-logreg", run_name="baseline-v1")
    train_model("sklearn-rf", experiment_name="pd-experiments")
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import yaml
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

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


class DemoTrendForecaster:
    """Lightweight monthly trend forecaster used when Prophet is unavailable."""

    def __init__(self) -> None:
        self._start_ds: pd.Timestamp | None = None
        self._history_ds: pd.Series | None = None
        self._train_len: int = 0
        self._coef: float = 0.0
        self._intercept: float = 0.0
        self._band: float = 0.01

    def fit(self, ts: pd.DataFrame) -> DemoTrendForecaster:
        hist = ts[["ds", "y"]].copy().sort_values("ds").reset_index(drop=True)
        hist["ds"] = pd.to_datetime(hist["ds"], errors="coerce")
        hist = hist.dropna(subset=["ds"])
        y = pd.to_numeric(hist["y"], errors="coerce").fillna(0.0).clip(0.0, 1.0).to_numpy()
        x = np.arange(len(y), dtype=float)
        if len(y) >= 2:
            self._coef, self._intercept = np.polyfit(x, y, 1)
            resid = y - (self._intercept + self._coef * x)
            self._band = float(max(np.std(resid), 0.01))
        elif len(y) == 1:
            self._coef = 0.0
            self._intercept = float(y[0])
            self._band = 0.01
        else:
            self._coef = 0.0
            self._intercept = 0.0
            self._band = 0.01
        self._history_ds = hist["ds"]
        self._start_ds = hist["ds"].iloc[0] if len(hist) else pd.Timestamp("2020-01-01")
        self._train_len = len(hist)
        return self

    def make_future_dataframe(
        self,
        periods: int,
        freq: str = "MS",
        include_history: bool = True,
    ) -> pd.DataFrame:
        if self._history_ds is None or len(self._history_ds) == 0:
            start = pd.Timestamp("2020-01-01")
            history = pd.Series([start])
        else:
            history = self._history_ds
            start = history.iloc[-1]
        future = pd.date_range(
            start=start + pd.offsets.MonthBegin(1),
            periods=periods,
            freq=freq,
        )
        if include_history:
            ds = pd.to_datetime(list(history) + list(future))
        else:
            ds = pd.to_datetime(list(future))
        return pd.DataFrame({"ds": ds})

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        out = frame.copy()
        ds = pd.to_datetime(out["ds"], errors="coerce")
        start = self._start_ds or pd.Timestamp("2020-01-01")
        month_idx = ((ds.dt.year - start.year) * 12 + (ds.dt.month - start.month)).astype(float)
        yhat = np.clip(self._intercept + self._coef * month_idx, 0.0, 1.0)
        out["yhat"] = yhat
        out["yhat_lower"] = np.clip(yhat - self._band, 0.0, 1.0)
        out["yhat_upper"] = np.clip(yhat + self._band, 0.0, 1.0)
        return out


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------


def train_model(
    model: str,
    run_name: str | None = None,
    experiment_name: str | None = None,
    namespace: str | None = None,
) -> Path:
    """Train a model, log everything to MLflow, and persist the artifact.

    Args:
        model:           Model identifier key.
        run_name:        Human-readable MLflow run label. Defaults to ``"<model>-run"``.
        experiment_name: MLflow experiment. Defaults to ``settings.mlflow_experiment_name``.

    Returns:
        Path to the saved artifact.

    Raises:
        ValueError: If ``model`` is not a recognised key.
        FileNotFoundError: If required processed data is not found.
    """
    experiment_name = experiment_name or settings.mlflow_experiment_name
    run_name = run_name or f"{model}-run"

    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(experiment_name)

    log.info(
        "train_model called: model={} experiment={} run_name={}",
        model,
        experiment_name,
        run_name,
    )

    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params(
            {
                "model": model,
                "random_seed": settings.random_seed,
                "test_split": settings.test_split,
                "forecast_horizon": settings.forecast_horizon,
            }
        )

        if model == "prophet":
            if namespace is None:
                path = _train_prophet(mlflow_run=run)
            else:
                path = _train_prophet(mlflow_run=run, namespace=namespace)
        elif model == "sklearn-logreg":
            if namespace is None:
                path = _train_sklearn(model_key="sklearn-logreg", use_rf=False, mlflow_run=run)
            else:
                path = _train_sklearn(
                    model_key="sklearn-logreg", use_rf=False, mlflow_run=run, namespace=namespace
                )
        elif model == "sklearn-rf":
            if namespace is None:
                path = _train_sklearn(model_key="sklearn-rf", use_rf=True, mlflow_run=run)
            else:
                path = _train_sklearn(
                    model_key="sklearn-rf", use_rf=True, mlflow_run=run, namespace=namespace
                )
        else:
            raise ValueError(
                f"Unknown model key '{model}'. "
                "Supported: 'prophet', 'sklearn-logreg', 'sklearn-rf'"
            )

        log.info("MLflow run complete: run_id={}", run.info.run_id)

    return path


# ---------------------------------------------------------------------------
# Prophet — aggregate delinquency-rate trend forecast
# ---------------------------------------------------------------------------


def _load_performance_parquet() -> tuple[pd.DataFrame, list[Path]]:
    with open(_DATA_PATHS) as fh:
        cfg = yaml.safe_load(fh)["fannie_mae"]
    perf_dir = Path(cfg["processed_dir"]) / "performance"
    paths = sorted(perf_dir.glob("*.parquet"))
    if not paths:
        raise FileNotFoundError(
            f"No performance parquet files in {perf_dir}. "
            "Run `pmai ingest --source fannie-mae` first."
        )
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True), paths


def _file_lineage(paths: list[Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in paths:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            while True:
                block = fh.read(1024 * 1024)
                if not block:
                    break
                h.update(block)
        records.append(
            {
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": h.hexdigest(),
            }
        )
    return records


def _build_delinquency_ts(perf_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate monthly delinquency rate from performance data.

    Returns a DataFrame with columns ``ds`` (datetime) and ``y`` (rate 0–1).
    """
    perf = perf_df.copy()
    perf["period"] = pd.to_numeric(perf["monthly_reporting_period"], errors="coerce")
    perf = perf.dropna(subset=["period"]).copy()
    # Zero-pad to 6 chars to restore stripped leading zeros
    perf["period"] = perf["period"].astype(int).astype(str).str.zfill(6)
    # Fannie Mae real data uses MMYYYY; seed/demo data uses YYYYMM.
    # Try YYYYMM first, fall back to MMYYYY for real ingested data.
    perf["ds"] = pd.to_datetime(perf["period"], format="%Y%m", errors="coerce").fillna(
        pd.to_datetime(perf["period"], format="%m%Y", errors="coerce")
    )
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


def _train_prophet(mlflow_run: Any = None, namespace: str | None = None) -> Path:
    """Fit Prophet on aggregate monthly delinquency rate and save artifact."""
    log.info("Loading performance data for Prophet training...")
    perf_df, perf_paths = _load_performance_parquet()
    ts = _build_delinquency_ts(perf_df)
    log.info("Time series built: {} monthly observations", len(ts))

    if len(ts) < 2:
        raise ValueError(
            f"Need at least 2 monthly observations to fit Prophet, got {len(ts)}. "
            "Ingest more performance quarters."
        )

    model_impl = "prophet"
    try:
        from prophet import Prophet  # import here to keep training import lightweight

        m = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0,
        )
        m.fit(ts)
    except Exception as exc:
        if not settings.low_memory_mode:
            raise
        log.warning(
            "Prophet unavailable in low-memory mode; falling back to DemoTrendForecaster: {}",
            exc,
        )
        model_impl = "demo-trend"
        m = DemoTrendForecaster().fit(ts)

    # Quick in-sample diagnostic
    future = m.make_future_dataframe(periods=settings.forecast_horizon, freq="MS")
    forecast = m.predict(future)
    in_sample = forecast[forecast["ds"].isin(ts["ds"])]
    actual = ts.set_index("ds")["y"]
    predicted = in_sample.set_index("ds")["yhat"]
    aligned = actual.align(predicted, join="inner")
    mae = float((aligned[0] - aligned[1]).abs().mean())
    log.info("Prophet in-sample MAE: {:.4f}", mae)

    if mlflow_run is not None:
        mlflow.log_metric("mae", mae)
        try:
            mlflow.sklearn.log_model(
                sk_model=m,
                name="model",
                registered_model_name=settings.mlflow_registered_model_name,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping MLflow model artifact log for forecast model: {}", exc)

    lineage_meta: dict[str, Any] = {
        "model_key": "prophet",
        "model_impl": model_impl,
        "metrics": {"mae": mae},
        "training_data_lineage": _file_lineage(perf_paths),
    }
    if mlflow_run is not None:
        lineage_meta["mlflow_run_id"] = mlflow_run.info.run_id

    artifact_path = save_model(
        m, "prophet", metadata=lineage_meta, set_active=True, namespace=namespace
    )
    log.info("Prophet model saved → {}", artifact_path)
    return artifact_path


# ---------------------------------------------------------------------------
# Sklearn — loan-level PD classification
# ---------------------------------------------------------------------------


def _load_feature_parquet() -> tuple[pd.DataFrame, Path]:
    with open(_DATA_PATHS) as fh:
        cfg = yaml.safe_load(fh)["fannie_mae"]
    feat_path = Path(cfg["processed_dir"]) / "features" / "features.parquet"
    if not feat_path.exists():
        raise FileNotFoundError(
            f"Feature parquet not found at {feat_path}. "
            "Run `pmai features --source fannie-mae` first."
        )
    return pd.read_parquet(feat_path), feat_path


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


def _train_sklearn(
    model_key: str,
    use_rf: bool,
    mlflow_run: Any = None,
    namespace: str | None = None,
) -> Path:
    """Fit a sklearn PD classifier and save the pipeline artifact."""
    log.info("Loading feature parquet for {} training...", model_key)
    feat_df, feat_path = _load_feature_parquet()

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

    if settings.low_memory_mode and len(X) > settings.low_memory_max_train_rows:
        max_rows = settings.low_memory_max_train_rows
        log.info(
            "Low-memory mode enabled: downsampling training frame from {:,} to {:,} rows",
            len(X),
            max_rows,
        )
        if y.nunique(dropna=True) > 1:
            sample_idx = (
                pd.DataFrame({"idx": X.index, "y": y})
                .groupby("y", group_keys=False)
                .apply(
                    lambda g: g.sample(
                        n=max(1, int(round(max_rows * len(g) / len(X)))),
                        random_state=settings.random_seed,
                    )
                )["idx"]
                .tolist()
            )
            sample_idx = sample_idx[:max_rows]
        else:
            sample_idx = (
                pd.Series(X.index).sample(n=max_rows, random_state=settings.random_seed).tolist()
            )
        X = X.loc[sample_idx].copy()
        y = y.loc[sample_idx].copy()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=settings.test_split,
        random_state=settings.random_seed,
        stratify=y,
    )
    log.info(
        "Train/test split: {:,} train / {:,} test (default rate: train={:.2%} test={:.2%})",
        len(X_train),
        len(X_test),
        y_train.mean(),
        y_test.mean(),
    )

    pipeline = _build_pd_pipeline(use_rf)
    pipeline.fit(X_train, y_train)

    y_pred_proba = pipeline.predict_proba(X_test)[:, 1]
    auc = float(roc_auc_score(y_test, y_pred_proba))
    log.info("{} test AUC: {:.4f}", model_key, auc)

    y_pred = (y_pred_proba >= 0.5).astype(int)
    report = classification_report(y_test, y_pred, output_dict=False)
    log.info("Classification report:\n{}", report)

    if mlflow_run is not None:
        mlflow.log_metrics({"auc": auc})
        mlflow.sklearn.log_model(
            sk_model=pipeline,
            name="model",
            registered_model_name=settings.mlflow_registered_model_name,
        )

    # Attach evaluation metadata so the registry can surface it
    artifact: dict[str, Any] = {
        "pipeline": pipeline,
        "feature_cols": feature_cols,
        "metrics": {"auc": auc},
        "model_key": model_key,
    }

    lineage_meta: dict[str, Any] = {
        "model_key": model_key,
        "metrics": {"auc": auc},
        "training_data_lineage": _file_lineage([feat_path]),
    }
    if mlflow_run is not None:
        lineage_meta["mlflow_run_id"] = mlflow_run.info.run_id

    path = save_model(
        artifact, model_key, metadata=lineage_meta, set_active=True, namespace=namespace
    )
    log.info("{} model saved → {} (AUC={:.4f})", model_key, path, auc)
    return path
