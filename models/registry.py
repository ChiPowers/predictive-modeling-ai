"""Local model registry with version history and active-model alias."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from config.settings import settings
from utils.logging import log

_ARTIFACTS_DIR = settings.models_dir


def _namespace_dir(namespace: str | None = None) -> Path:
    if namespace is None:
        return _ARTIFACTS_DIR
    safe = namespace.strip().replace("/", "_")
    return _ARTIFACTS_DIR / "users" / safe


def _manifest_path(namespace: str | None = None) -> Path:
    return _namespace_dir(namespace) / "registry_manifest.json"


def _active_path(namespace: str | None = None) -> Path:
    return _namespace_dir(namespace) / "active_model.json"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            block = fh.read(1024 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def _load_manifest(namespace: str | None = None) -> dict[str, Any]:
    path = _manifest_path(namespace)
    if not path.exists():
        return {"models": {}, "latest": {}}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"models": {}, "latest": {}}


def _save_manifest(data: dict[str, Any], namespace: str | None = None) -> None:
    _namespace_dir(namespace).mkdir(parents=True, exist_ok=True)
    _manifest_path(namespace).write_text(json.dumps(data, indent=2))


def save(
    model: Any,
    name: str,
    *,
    metadata: dict[str, Any] | None = None,
    set_active: bool = False,
    namespace: str | None = None,
) -> Path:
    """Persist a model artifact using joblib."""
    import joblib

    base_dir = _namespace_dir(namespace)
    base_dir.mkdir(parents=True, exist_ok=True)
    alias_path = base_dir / f"{name}.joblib"
    joblib.dump(model, alias_path)

    version_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:8]}"
    version_filename = f"{name}__{version_id}.joblib"
    version_path = base_dir / version_filename
    shutil.copy2(alias_path, version_path)

    manifest = _load_manifest(namespace)
    model_versions = manifest.setdefault("models", {}).setdefault(name, [])
    entry: dict[str, Any] = {
        "name": name,
        "version_id": version_id,
        "created_at": _utc_now(),
        "artifact_path": str(version_path),
        "artifact_filename": version_filename,
        "sha256": _sha256(version_path),
        "metadata": metadata or {},
    }
    model_versions.append(entry)
    manifest.setdefault("latest", {})[name] = version_id
    _save_manifest(manifest, namespace)

    if set_active:
        activate(name, version_id, namespace=namespace)

    log.info("Model saved: ns={} alias={} version={}", namespace or "global", alias_path, version_filename)
    return alias_path


def load(name: str, version_id: str | None = None, namespace: str | None = None) -> Any:
    """Load a model artifact by name."""
    import joblib

    if version_id is not None:
        versions = get_versions(name, namespace=namespace)
        match = next((v for v in versions if v["version_id"] == version_id), None)
        if match is None:
            raise FileNotFoundError(f"Model version not found: {name}:{version_id}")
        path = Path(match["artifact_path"])
    else:
        path = _namespace_dir(namespace) / f"{name}.joblib"

    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}")
    log.info("Loading model from {}", path)
    return joblib.load(path)


def get_versions(name: str, namespace: str | None = None) -> list[dict[str, Any]]:
    manifest = _load_manifest(namespace)
    versions = manifest.get("models", {}).get(name, [])
    return sorted(versions, key=lambda v: v.get("created_at", ""), reverse=True)


def list_models(namespace: str | None = None) -> list[dict[str, Any]]:
    manifest = _load_manifest(namespace)
    latest_map: dict[str, str] = manifest.get("latest", {})
    out: list[dict[str, Any]] = []
    for name, versions in manifest.get("models", {}).items():
        latest_version = latest_map.get(name)
        out.append({
            "name": name,
            "version_count": len(versions),
            "latest_version_id": latest_version,
        })
    return sorted(out, key=lambda m: m["name"])


def activate(name: str, version_id: str | None = None, *, namespace: str | None = None) -> dict[str, Any]:
    """Set active model alias and write `current.joblib`."""
    versions = get_versions(name, namespace=namespace)
    if not versions:
        raise FileNotFoundError(f"No versions found for model '{name}'")

    target = versions[0] if version_id is None else next(
        (v for v in versions if v["version_id"] == version_id), None
    )
    if target is None:
        raise FileNotFoundError(f"Model version not found: {name}:{version_id}")

    source = Path(target["artifact_path"])
    if not source.exists():
        raise FileNotFoundError(f"Artifact file missing for activation: {source}")

    base_dir = _namespace_dir(namespace)
    base_dir.mkdir(parents=True, exist_ok=True)
    current_path = base_dir / "current.joblib"
    shutil.copy2(source, current_path)
    active = {
        "name": name,
        "version_id": target["version_id"],
        "artifact_path": str(source),
        "current_alias_path": str(current_path),
        "updated_at": _utc_now(),
        "namespace": namespace,
    }
    _active_path(namespace).write_text(json.dumps(active, indent=2))
    log.info("Activated model ns={} {}:{} -> {}", namespace or "global", name, target["version_id"], current_path)
    return active


def get_active(namespace: str | None = None) -> dict[str, Any] | None:
    path = _active_path(namespace)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
