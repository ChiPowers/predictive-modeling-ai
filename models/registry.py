"""Model registry — load and save serialised model artifacts."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from config.settings import settings
from utils.logging import log

_ARTIFACTS_DIR = settings.models_dir


def save(model: Any, name: str) -> Path:
    """Persist a model artifact using joblib.

    Args:
        model: Fitted estimator / pipeline.
        name:  Artifact filename (without extension).

    Returns:
        Path where the artifact was written.
    """
    import joblib

    _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _ARTIFACTS_DIR / f"{name}.joblib"
    joblib.dump(model, path)
    log.info("Model saved to {}", path)
    return path


def load(name: str) -> Any:
    """Load a model artifact by name.

    Args:
        name: Artifact filename (without extension).

    Returns:
        Deserialised model object.
    """
    import joblib

    path = _ARTIFACTS_DIR / f"{name}.joblib"
    if not path.exists():
        raise FileNotFoundError(f"Model artifact not found: {path}")
    log.info("Loading model from {}", path)
    return joblib.load(path)
