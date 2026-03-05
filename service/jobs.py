"""Background job orchestration for long-running backend tasks."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(value: Any) -> Any:
    """Convert non-JSON-native values into serializable representations."""
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, tuple):
        return [_normalize(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class JobManager:
    """In-process async job runner with simple lifecycle tracking."""

    def __init__(self, max_workers: int = 2) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="pmai-job")
        self._lock = Lock()
        self._jobs: dict[str, dict[str, Any]] = {}

    def submit(
        self,
        job_type: str,
        payload: dict[str, Any],
        fn: Callable[[], Any],
        *,
        owner: str | None = None,
    ) -> dict[str, Any]:
        job_id = uuid4().hex
        job: dict[str, Any] = {
            "id": job_id,
            "job_type": job_type,
            "owner": owner,
            "status": "queued",
            "created_at": _utc_now_iso(),
            "started_at": None,
            "finished_at": None,
            "input_payload": _normalize(payload),
            "result": None,
            "error": None,
        }
        with self._lock:
            self._jobs[job_id] = job
        self._pool.submit(self._run, job_id, fn)
        return job

    def _run(self, job_id: str, fn: Callable[[], Any]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job["status"] = "running"
            job["started_at"] = _utc_now_iso()
        try:
            result = fn()
            with self._lock:
                job = self._jobs[job_id]
                job["status"] = "succeeded"
                job["finished_at"] = _utc_now_iso()
                job["result"] = _normalize(result)
        except Exception as exc:
            with self._lock:
                job = self._jobs[job_id]
                job["status"] = "failed"
                job["finished_at"] = _utc_now_iso()
                job["error"] = str(exc)

    def get(self, job_id: str, owner: str | None = None) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if owner is not None and job.get("owner") != owner:
                return None
            return dict(job)

    def list(self, limit: int = 50, owner: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            jobs = list(self._jobs.values())
        if owner is not None:
            jobs = [j for j in jobs if j.get("owner") == owner]
        jobs_sorted = sorted(jobs, key=lambda j: j["created_at"], reverse=True)
        return [dict(j) for j in jobs_sorted[:limit]]


job_manager = JobManager()
