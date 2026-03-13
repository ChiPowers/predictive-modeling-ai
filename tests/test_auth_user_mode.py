"""Tests for auth flow and user-scoped modeling endpoints."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import service.api as api
import service.auth as auth
from service.jobs import JobManager


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(auth, "_DB_PATH", tmp_path / "users.sqlite3")
    monkeypatch.setattr(api, "job_manager", JobManager(max_workers=1))
    return TestClient(api.app, raise_server_exceptions=False)


def _register_and_login(client: TestClient, username: str, password: str) -> str:
    r = client.post("/auth/register", json={"username": username, "password": password})
    assert r.status_code == 201
    login = client.post("/auth/login", json={"username": username, "password": password})
    assert login.status_code == 200
    return login.json()["access_token"]


def test_auth_register_login_me(client: TestClient) -> None:
    token = _register_and_login(client, "alice", "password123")
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_me_jobs_require_auth(client: TestClient) -> None:
    resp = client.get("/me/jobs")
    assert resp.status_code == 401


def test_me_jobs_are_user_scoped(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    import training.trainer as trainer

    monkeypatch.setattr(
        trainer,
        "train_model",
        lambda *args, **kwargs: Path("models/artifacts/users/alice/sklearn-rf.joblib"),
    )

    token_a = _register_and_login(client, "alice", "password123")
    token_b = _register_and_login(client, "bob", "password123")

    created = client.post(
        "/me/jobs/train",
        json={"model": "sklearn-rf"},
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert created.status_code == 202
    job_id = created.json()["id"]

    jobs_a = client.get("/me/jobs", headers={"Authorization": f"Bearer {token_a}"})
    assert jobs_a.status_code == 200
    assert any(j["id"] == job_id for j in jobs_a.json()["jobs"])

    jobs_b = client.get("/me/jobs", headers={"Authorization": f"Bearer {token_b}"})
    assert jobs_b.status_code == 200
    assert all(j["id"] != job_id for j in jobs_b.json()["jobs"])
