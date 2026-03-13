"""Tests for training/train_xgb.py."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
import pytest

pytest.importorskip("xgboost", reason="xgboost not installed")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_data(n: int = 200, p: int = 10, seed: int = 0) -> tuple[Any, Any]:
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, p))
    y = (rng.random(n) > 0.7).astype(int)
    return X, y


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


def test_train_xgb_returns_expected_keys(tmp_path, monkeypatch):
    """train_xgb returns a dict with model, best_params, metrics."""
    monkeypatch.chdir(tmp_path)

    from training.train_xgb import train_xgb

    X, y = _make_data()
    split = int(0.8 * len(X))
    result = train_xgb(X[:split], y[:split], X[split:], y[split:], n_iter=3, cv=2)

    assert set(result.keys()) == {"model", "best_params", "metrics"}
    assert "roc_auc" in result["metrics"]
    assert "brier_score" in result["metrics"]
    assert "log_loss" in result["metrics"]


def test_train_xgb_writes_metrics_json(tmp_path, monkeypatch):
    """reports/xgb_metrics.json is written and parseable."""
    monkeypatch.chdir(tmp_path)

    from training.train_xgb import train_xgb

    X, y = _make_data()
    split = int(0.8 * len(X))
    train_xgb(X[:split], y[:split], X[split:], y[split:], n_iter=3, cv=2)

    metrics_file = tmp_path / "reports" / "xgb_metrics.json"
    assert metrics_file.exists(), "reports/xgb_metrics.json was not created"

    payload = json.loads(metrics_file.read_text())
    assert "metrics" in payload
    assert "best_params" in payload
    assert 0.0 <= payload["metrics"]["roc_auc"] <= 1.0


def test_train_xgb_saves_model_artifact(tmp_path, monkeypatch):
    """The best model is persisted as a joblib artifact."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "models" / "artifacts").mkdir(parents=True)

    from training.train_xgb import train_xgb

    X, y = _make_data()
    split = int(0.8 * len(X))
    train_xgb(
        X[:split],
        y[:split],
        X[split:],
        y[split:],
        n_iter=2,
        cv=2,
        artifact_name="test_xgb",
    )

    artifact = tmp_path / "models" / "artifacts" / "test_xgb.joblib"
    assert artifact.exists(), f"Expected artifact at {artifact}"
