"""Contract tests for frontend-facing API metadata endpoints."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

import service.api as api


def test_metadata_contract(monkeypatch) -> None:
    """GET /metadata returns a stable contract payload for the frontend."""
    monkeypatch.setattr(api, "_is_real_data_mode", lambda: False)
    client = TestClient(api.app, raise_server_exceptions=False)

    resp = client.get("/metadata")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["app_name"] == "predictive-modeling-ai"
    assert payload["mode"] == "demo"
    assert "capabilities" in payload
    assert "artifacts" in payload
    names = {item["name"] for item in payload["artifacts"]}
    assert names == {"prophet", "sklearn-logreg", "sklearn-rf"}


def test_ready_returns_not_ready_when_model_unloaded(monkeypatch) -> None:
    """GET /ready returns 503 until scoring model is loaded."""
    monkeypatch.setattr(type(api.scoring_model), "is_loaded", property(lambda self: False))
    client = TestClient(api.app, raise_server_exceptions=False)
    resp = client.get("/ready")
    assert resp.status_code == 503
    payload = resp.json()
    assert payload["status"] == "not_ready"
    assert payload["checks"]["model_loaded"] is False


def test_ui_root_serves_html() -> None:
    """GET / serves the frontend HTML shell."""
    client = TestClient(api.app, raise_server_exceptions=False)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "Mortgage Risk Ops Console" in resp.text


def test_ui_static_css_served() -> None:
    """Frontend CSS bundle is available via /static."""
    client = TestClient(api.app, raise_server_exceptions=False)
    resp = client.get("/static/styles.css")
    assert resp.status_code == 200
    assert "text/css" in resp.headers.get("content-type", "")


def test_monitoring_summary_unavailable(tmp_path: Path, monkeypatch) -> None:
    """GET /monitoring/summary returns available=false when no reports exist."""
    monkeypatch.setattr(api, "_MONITORING_DIR", tmp_path)
    client = TestClient(api.app, raise_server_exceptions=False)

    resp = client.get("/monitoring/summary")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["available"] is False
    assert payload["summary_markdown"] is None


def test_monitoring_summary_loads_reports(tmp_path: Path, monkeypatch) -> None:
    """GET /monitoring/summary loads markdown + JSON report artifacts."""
    mon = tmp_path / "monitoring"
    mon.mkdir(parents=True)
    (mon / "summary.md").write_text("# Monitoring Summary")
    (mon / "drift_features.json").write_text(json.dumps({"credit_score": {"severity": "ok"}}))
    (mon / "score_drift.json").write_text(json.dumps({"severity": "warning"}))
    (mon / "perf_drift.json").write_text(json.dumps({"latest_auc": 0.71}))
    monkeypatch.setattr(api, "_MONITORING_DIR", mon)

    client = TestClient(api.app, raise_server_exceptions=False)
    resp = client.get("/monitoring/summary")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["available"] is True
    assert payload["summary_markdown"] == "# Monitoring Summary"
    assert payload["drift_features"]["credit_score"]["severity"] == "ok"
    assert payload["score_drift"]["severity"] == "warning"
    assert payload["perf_drift"]["latest_auc"] == 0.71
