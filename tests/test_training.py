"""Tests for training/trainer.py."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# train_model routing
# ---------------------------------------------------------------------------


def test_train_unknown_model_raises_value_error() -> None:
    from training.trainer import train_model

    with pytest.raises(ValueError, match="Unknown model key"):
        train_model("xgboost-not-implemented")


# ---------------------------------------------------------------------------
# _make_default_label
# ---------------------------------------------------------------------------


def test_make_default_label_from_max_dpd() -> None:
    from training.trainer import _make_default_label

    df = pd.DataFrame({"max_dpd": [0, 1, 2, 3, 4, np.nan]})
    labels = _make_default_label(df)
    # DPD >= 3 is default
    assert list(labels) == [0, 0, 0, 1, 1, 0]


def test_make_default_label_from_zero_balance_code() -> None:
    from training.trainer import _make_default_label

    df = pd.DataFrame({"zero_balance_code": ["01", "02", "03", "06", "96", ""]})
    labels = _make_default_label(df)
    # 02, 03, 06 are default codes
    assert list(labels) == [0, 1, 1, 1, 0, 0]


def test_make_default_label_synthetic_fallback() -> None:
    """With no label column, returns a synthetic 5% default series."""
    from training.trainer import _make_default_label

    df = pd.DataFrame({"some_other_col": range(1000)})
    labels = _make_default_label(df)
    assert len(labels) == 1000
    # Rough check: synthetic rate should be near 5%
    assert 0.01 < labels.mean() < 0.15


# ---------------------------------------------------------------------------
# _build_delinquency_ts
# ---------------------------------------------------------------------------


def _make_perf_df(n_periods: int = 6, n_loans_per_period: int = 100) -> pd.DataFrame:
    periods = [f"2020{m:02d}" for m in range(1, n_periods + 1)]
    records = []
    rng = np.random.default_rng(42)
    for p in periods:
        for _ in range(n_loans_per_period):
            status = rng.choice([0, 0, 0, 0, 1, 2, 3], p=[0.8, 0.1, 0.04, 0.02, 0.02, 0.01, 0.01])
            records.append({"monthly_reporting_period": p, "current_delinquency_status": str(status)})
    return pd.DataFrame(records)


def test_build_delinquency_ts_shape() -> None:
    from training.trainer import _build_delinquency_ts

    perf = _make_perf_df(6)
    ts = _build_delinquency_ts(perf)
    assert set(ts.columns) == {"ds", "y"}
    assert len(ts) == 6


def test_build_delinquency_ts_rate_bounded() -> None:
    from training.trainer import _build_delinquency_ts

    perf = _make_perf_df()
    ts = _build_delinquency_ts(perf)
    assert (ts["y"] >= 0).all()
    assert (ts["y"] <= 1).all()


def test_build_delinquency_ts_sorted() -> None:
    from training.trainer import _build_delinquency_ts

    perf = _make_perf_df()
    ts = _build_delinquency_ts(perf)
    assert ts["ds"].is_monotonic_increasing


# ---------------------------------------------------------------------------
# _build_pd_pipeline
# ---------------------------------------------------------------------------


def test_build_pd_pipeline_logreg() -> None:
    from sklearn.linear_model import LogisticRegression

    from training.trainer import _build_pd_pipeline

    pipe = _build_pd_pipeline(use_rf=False)
    assert any(isinstance(s, LogisticRegression) for _, s in pipe.steps)


def test_build_pd_pipeline_rf() -> None:
    from sklearn.ensemble import RandomForestClassifier

    from training.trainer import _build_pd_pipeline

    pipe = _build_pd_pipeline(use_rf=True)
    assert any(isinstance(s, RandomForestClassifier) for _, s in pipe.steps)


def test_pd_pipeline_fits_synthetic_data() -> None:
    from training.trainer import _build_pd_pipeline

    rng = np.random.default_rng(0)
    X = pd.DataFrame(rng.normal(size=(200, 5)), columns=[f"f{i}" for i in range(5)])
    y = (rng.random(200) > 0.8).astype(int)

    pipe = _build_pd_pipeline(use_rf=False)
    pipe.fit(X, y)
    proba = pipe.predict_proba(X)
    assert proba.shape == (200, 2)
    assert ((proba >= 0) & (proba <= 1)).all()


# ---------------------------------------------------------------------------
# _train_sklearn — integration with mocked data
# ---------------------------------------------------------------------------


def _make_feature_df(n: int = 300) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    return pd.DataFrame({
        "credit_score": rng.integers(580, 800, n).astype(float),
        "orig_ltv": rng.uniform(50, 97, n),
        "orig_dti": rng.uniform(20, 50, n),
        "orig_upb": rng.uniform(100_000, 750_000, n),
        "orig_interest_rate": rng.uniform(3, 8, n),
        "orig_loan_term": rng.choice([180, 360], n).astype(float),
        "log_upb": rng.uniform(11, 13.5, n),
        "is_first_time_homebuyer": rng.choice([0.0, 1.0], n),
        "is_high_ltv": rng.choice([0.0, 1.0], n),
        "is_high_dti": rng.choice([0.0, 1.0], n),
        "is_arm": rng.choice([0.0, 1.0], n),
        "is_jumbo": rng.choice([0.0, 1.0], n),
        "occupancy_code": rng.choice([0, 1, 2], n).astype(float),
        "loan_purpose_code": rng.choice([0, 1, 2, 3], n).astype(float),
        "channel_code": rng.choice([0, 1, 2, 3], n).astype(float),
        "property_type_code": rng.choice([0, 1, 2], n).astype(float),
        "max_dpd": rng.choice([0, 1, 2, 3, 6], n, p=[0.8, 0.07, 0.05, 0.04, 0.04]).astype(float),
    })


def test_train_sklearn_logreg(tmp_path: Path, monkeypatch) -> None:
    """_train_sklearn runs end-to-end on synthetic data and saves an artifact."""
    import models.registry as reg
    from training import trainer

    feat_df = _make_feature_df(300)

    monkeypatch.setattr(trainer, "_load_feature_parquet", lambda: feat_df)
    monkeypatch.setattr(reg, "_ARTIFACTS_DIR", tmp_path)

    path = trainer._train_sklearn("sklearn-logreg", use_rf=False)
    assert path.exists()
    artifact = reg.load("sklearn-logreg")
    assert "pipeline" in artifact
    assert "metrics" in artifact
    assert 0.0 <= artifact["metrics"]["auc"] <= 1.0  # valid AUC range


def test_train_sklearn_rf(tmp_path: Path, monkeypatch) -> None:
    import models.registry as reg
    from training import trainer

    feat_df = _make_feature_df(300)

    monkeypatch.setattr(trainer, "_load_feature_parquet", lambda: feat_df)
    monkeypatch.setattr(reg, "_ARTIFACTS_DIR", tmp_path)

    path = trainer._train_sklearn("sklearn-rf", use_rf=True)
    assert path.exists()
    artifact = reg.load("sklearn-rf")
    assert artifact["model_key"] == "sklearn-rf"


def test_train_model_logreg_end_to_end(tmp_path: Path, monkeypatch) -> None:
    """Public train_model('sklearn-logreg') dispatches correctly."""
    import models.registry as reg
    from training import trainer

    feat_df = _make_feature_df(300)
    monkeypatch.setattr(trainer, "_load_feature_parquet", lambda: feat_df)
    monkeypatch.setattr(reg, "_ARTIFACTS_DIR", tmp_path)

    path = trainer.train_model("sklearn-logreg")
    assert path.exists()


# ---------------------------------------------------------------------------
# _train_prophet — integration with mocked performance data
# ---------------------------------------------------------------------------


@pytest.mark.xfail(reason="prophet 1.1.5 uses np.float_ removed in NumPy 2.0; pin numpy<2 to fix")
def test_train_prophet(tmp_path: Path, monkeypatch) -> None:
    """_train_prophet fits Prophet on synthetic monthly delinquency data."""
    import models.registry as reg
    from training import trainer

    perf_df = _make_perf_df(n_periods=24, n_loans_per_period=100)
    monkeypatch.setattr(trainer, "_load_performance_parquet", lambda: perf_df)
    monkeypatch.setattr(reg, "_ARTIFACTS_DIR", tmp_path)

    path = trainer._train_prophet()
    assert path.exists()


def test_train_prophet_too_few_periods_raises(tmp_path: Path, monkeypatch) -> None:
    """Prophet raises ValueError when fewer than 2 monthly observations exist."""
    from training import trainer

    perf_df = _make_perf_df(n_periods=1, n_loans_per_period=5)
    monkeypatch.setattr(trainer, "_load_performance_parquet", lambda: perf_df)

    with pytest.raises(ValueError, match="2 monthly observations"):
        trainer._train_prophet()
