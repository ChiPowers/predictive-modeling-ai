"""API tests for background job orchestration endpoints."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import service.api as api
from service.jobs import JobManager


def _wait_for_terminal(client: TestClient, job_id: str, timeout_s: float = 2.0) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/jobs/{job_id}")
        assert resp.status_code == 200
        payload = resp.json()
        if payload["status"] in {"succeeded", "failed"}:
            return payload
        time.sleep(0.02)
    raise AssertionError(f"Job {job_id} did not complete in {timeout_s}s")


@pytest.fixture()
def isolated_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "job_manager", JobManager(max_workers=1))


def test_train_job_succeeds(monkeypatch: pytest.MonkeyPatch, isolated_jobs: None) -> None:
    import training.trainer as trainer

    monkeypatch.setattr(
        trainer, "train_model", lambda *args, **kwargs: Path("models/artifacts/mock.joblib")
    )
    client = TestClient(api.app, raise_server_exceptions=False)

    created = client.post("/jobs/train", json={"model": "sklearn-rf"})
    assert created.status_code == 202
    job_id = created.json()["id"]

    final = _wait_for_terminal(client, job_id)
    assert final["status"] == "succeeded"
    assert final["result"]["model"] == "sklearn-rf"
    assert final["result"]["artifact_path"].endswith("mock.joblib")


def test_train_job_failure(monkeypatch: pytest.MonkeyPatch, isolated_jobs: None) -> None:
    import training.trainer as trainer

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(trainer, "train_model", _boom)
    client = TestClient(api.app, raise_server_exceptions=False)

    created = client.post("/jobs/train", json={"model": "sklearn-rf"})
    assert created.status_code == 202
    job_id = created.json()["id"]

    final = _wait_for_terminal(client, job_id)
    assert final["status"] == "failed"
    assert "simulated failure" in final["error"]


def test_list_jobs_contains_submitted_job(
    monkeypatch: pytest.MonkeyPatch, isolated_jobs: None
) -> None:
    import training.trainer as trainer

    monkeypatch.setattr(
        trainer, "train_model", lambda *args, **kwargs: Path("models/artifacts/mock.joblib")
    )
    client = TestClient(api.app, raise_server_exceptions=False)

    created = client.post("/jobs/train", json={"model": "prophet"})
    assert created.status_code == 202
    job_id = created.json()["id"]
    _wait_for_terminal(client, job_id)

    listed = client.get("/jobs")
    assert listed.status_code == 200
    jobs = listed.json()["jobs"]
    assert any(j["id"] == job_id for j in jobs)


def test_seed_demo_job_succeeds(monkeypatch: pytest.MonkeyPatch, isolated_jobs: None) -> None:
    monkeypatch.setattr(
        api,
        "_run_seed_demo_job",
        lambda req: {"path": "data/raw/fannie_mae/combined/demo_2025Q1.csv", "rows": 1000},
    )
    client = TestClient(api.app, raise_server_exceptions=False)

    created = client.post("/jobs/seed-demo", json={})
    assert created.status_code == 202
    job_id = created.json()["id"]

    final = _wait_for_terminal(client, job_id)
    assert final["status"] == "succeeded"
    assert final["result"]["path"].endswith("demo_2025Q1.csv")
