"""Smoke tests for the FastAPI prediction service."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from service.api import app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


def test_health_ok(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /forecast — model not found
# ---------------------------------------------------------------------------


def test_forecast_no_artifact_returns_404(client: TestClient) -> None:
    """404 when the prophet artifact does not exist yet."""
    from unittest.mock import patch

    import models.registry as reg

    with patch.object(reg, "load", side_effect=FileNotFoundError("not found")):
        resp = client.post(
            "/forecast",
            json={"source": "fannie-mae", "model": "prophet", "horizon": 3},
        )
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_forecast_invalid_payload_returns_422(client: TestClient) -> None:
    """POST /forecast with a missing required field returns 422."""
    resp = client.post("/forecast", json={})
    assert resp.status_code == 422


@pytest.mark.xfail(reason="prophet 1.1.5 uses np.float_ removed in NumPy 2.0; pin numpy<2 to fix")
def test_forecast_with_real_prophet(tmp_path: Path, client: TestClient) -> None:
    """End-to-end: train a tiny Prophet model, load it, assert 200."""
    from prophet import Prophet

    import models.registry as reg

    # Fit a minimal Prophet model
    ts = pd.DataFrame({
        "ds": pd.date_range("2020-01-01", periods=24, freq="MS"),
        "y": np.random.default_rng(0).uniform(0.01, 0.10, 24),
    })
    m = Prophet(yearly_seasonality=False, weekly_seasonality=False, daily_seasonality=False)
    m.fit(ts)

    with patch.object(reg, "_ARTIFACTS_DIR", tmp_path):
        reg.save(m, "prophet")
        with patch.object(reg, "_ARTIFACTS_DIR", tmp_path):
            resp = client.post(
                "/forecast",
                json={"source": "fannie-mae", "model": "prophet", "horizon": 6},
            )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["model"] == "prophet"
    assert body["periods"] == 6
    assert len(body["forecast"]) == 6
    first = body["forecast"][0]
    assert {"ds", "yhat", "yhat_lower", "yhat_upper"} == set(first.keys())
    assert 0.0 <= first["yhat"] <= 1.0


# ---------------------------------------------------------------------------
# /score — sklearn PD model
# ---------------------------------------------------------------------------


def _make_sklearn_artifact() -> dict:
    """Build a tiny trained sklearn artifact for testing."""
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    rng = np.random.default_rng(5)
    feature_cols = ["credit_score", "orig_ltv", "orig_dti"]
    X = rng.normal(size=(200, 3))
    y = (rng.random(200) > 0.85).astype(int)
    pipe = Pipeline([("imputer", SimpleImputer()), ("clf", LogisticRegression(max_iter=200))])
    pipe.fit(X, y)
    return {"pipeline": pipe, "feature_cols": feature_cols, "model_key": "sklearn-logreg"}


def test_score_no_artifact_returns_404(client: TestClient) -> None:
    import models.registry as reg

    with patch.object(reg, "load", side_effect=FileNotFoundError("not found")):
        resp = client.post(
            "/score",
            json={"model": "sklearn-logreg", "loans": [{"credit_score": 720}]},
        )
    assert resp.status_code == 404


def test_score_empty_loans_returns_422(client: TestClient) -> None:
    resp = client.post("/score", json={"model": "sklearn-logreg", "loans": []})
    assert resp.status_code == 422


def test_score_with_real_model(tmp_path: Path, client: TestClient) -> None:
    """End-to-end: save a real sklearn artifact and POST /score."""
    import models.registry as reg

    artifact = _make_sklearn_artifact()
    with patch.object(reg, "_ARTIFACTS_DIR", tmp_path):
        reg.save(artifact, "sklearn-logreg")
        with patch.object(reg, "_ARTIFACTS_DIR", tmp_path):
            resp = client.post(
                "/score",
                json={
                    "model": "sklearn-logreg",
                    "loans": [
                        {"credit_score": 720, "orig_ltv": 80.0, "orig_dti": 35.0},
                        {"credit_score": 600, "orig_ltv": 95.0, "orig_dti": 50.0},
                    ],
                },
            )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["n_loans"] == 2
    assert len(body["scores"]) == 2
    for s in body["scores"]:
        assert 0.0 <= s <= 1.0


def test_score_missing_feature_columns_filled_with_nan(tmp_path: Path, client: TestClient) -> None:
    """Loans missing expected feature columns should still score (NaN → imputer)."""
    import models.registry as reg

    artifact = _make_sklearn_artifact()
    with patch.object(reg, "_ARTIFACTS_DIR", tmp_path):
        reg.save(artifact, "sklearn-logreg")
        with patch.object(reg, "_ARTIFACTS_DIR", tmp_path):
            resp = client.post(
                "/score",
                json={
                    "model": "sklearn-logreg",
                    "loans": [{"credit_score": 700}],  # missing orig_ltv and orig_dti
                },
            )
    assert resp.status_code == 200
    assert len(resp.json()["scores"]) == 1
