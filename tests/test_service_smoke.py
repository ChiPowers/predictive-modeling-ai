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
    assert resp.json() == {"status": "ok"}


def test_forecast_stub_returns_500(client: TestClient) -> None:
    """POST /forecast returns 500 until the endpoint is implemented."""
    resp = client.post(
        "/forecast",
        json={"source": "csv:data/raw/sample.csv", "model": "prophet", "horizon": 7},
    )
    assert resp.status_code == 500


def test_forecast_invalid_payload_returns_422(client: TestClient) -> None:
    """POST /forecast with a missing required field returns 422."""
    resp = client.post("/forecast", json={})
    assert resp.status_code == 422
