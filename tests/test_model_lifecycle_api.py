"""API tests for model lifecycle endpoints."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sklearn.linear_model import LinearRegression

import service.api as api
from models import registry


@pytest.fixture()
def client_with_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(registry, "_ARTIFACTS_DIR", tmp_path)
    return TestClient(api.app, raise_server_exceptions=False)


def test_models_catalog_and_activate_flow(
    client_with_registry: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []

    def _fake_load(path: Path | None = None, filename: str | None = None) -> None:
        calls.append((str(path), str(filename)))

    monkeypatch.setattr(api.scoring_model, "load", _fake_load)  # type: ignore[attr-defined]

    model = LinearRegression().fit([[1], [2]], [2.0, 4.0])
    registry.save(model, "lr")

    resp = client_with_registry.get("/models")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["models"][0]["name"] == "lr"
    latest = payload["models"][0]["latest_version_id"]
    assert latest is not None

    versions = client_with_registry.get("/models/lr/versions")
    assert versions.status_code == 200
    assert versions.json()[0]["version_id"] == latest

    activated = client_with_registry.post("/models/activate", json={"name": "lr"})
    assert activated.status_code == 200
    assert activated.json()["name"] == "lr"
    assert len(calls) == 1

    active = client_with_registry.get("/models/active")
    assert active.status_code == 200
    assert active.json()["name"] == "lr"


def test_active_model_404_when_unset(client_with_registry: TestClient) -> None:
    resp = client_with_registry.get("/models/active")
    assert resp.status_code == 404
