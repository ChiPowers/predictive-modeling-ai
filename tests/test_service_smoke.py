"""Smoke tests for the FastAPI prediction service."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from service.api import app


@pytest.fixture()
def client() -> TestClient:
    """TestClient with server exceptions surfaced as HTTP 500 (not re-raised)."""
    return TestClient(app, raise_server_exceptions=False)


def test_health_ok(client: TestClient) -> None:
    """GET /health returns 200 with status ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["status"] == "ok"
    assert "model_loaded" in payload


def test_forecast_missing_model_returns_503(client: TestClient) -> None:
    """POST /forecast returns 503 when the prophet artifact is not present."""
    resp = client.post(
        "/forecast",
        json={"source": "csv:data/raw/sample.csv", "model": "prophet", "horizon": 7},
    )
    assert resp.status_code == 503


def test_forecast_invalid_payload_returns_422(client: TestClient) -> None:
    """POST /forecast with a missing required field returns 422."""
    resp = client.post("/forecast", json={})
    assert resp.status_code == 422
