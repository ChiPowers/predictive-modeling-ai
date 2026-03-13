"""Tests for models.registry: save, load, and predict cycle."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from sklearn.linear_model import LinearRegression

from models import registry


@pytest.fixture(autouse=True)
def _patch_artifacts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect artifact storage to a temp directory for each test."""
    monkeypatch.setattr(registry, "_ARTIFACTS_DIR", tmp_path)


def test_save_creates_joblib_file(tmp_path: Path) -> None:
    """save() writes a .joblib file and returns its path."""
    model = LinearRegression().fit([[1], [2]], [2.0, 4.0])
    path = registry.save(model, "lr")
    assert path == tmp_path / "lr.joblib"
    assert path.exists()


def test_load_returns_correct_type() -> None:
    """load() deserialises the saved model."""
    model = LinearRegression().fit([[1], [2]], [2.0, 4.0])
    registry.save(model, "lr")
    loaded = registry.load("lr")
    assert isinstance(loaded, LinearRegression)


def test_load_predict_tiny_sample() -> None:
    """Saved model can be loaded and used for inference on a tiny sample."""
    X_train = np.array([[1], [2], [3], [4], [5]], dtype=float)
    y_train = np.array([2.0, 4.0, 6.0, 8.0, 10.0])
    model = LinearRegression().fit(X_train, y_train)
    registry.save(model, "lr")

    loaded = registry.load("lr")
    preds = loaded.predict([[6], [7]])
    np.testing.assert_allclose(preds, [12.0, 14.0], atol=1e-5)


def test_load_missing_artifact_raises_file_not_found() -> None:
    """load() raises FileNotFoundError for an artifact that does not exist."""
    with pytest.raises(FileNotFoundError, match="Model artifact not found"):
        registry.load("does-not-exist")


def test_save_creates_version_manifest_entry() -> None:
    """save() writes versioned metadata to the local manifest."""
    model = LinearRegression().fit([[1], [2]], [2.0, 4.0])
    registry.save(model, "lr", metadata={"metrics": {"mae": 0.1}})

    versions = registry.get_versions("lr")
    assert len(versions) == 1
    assert versions[0]["name"] == "lr"
    assert versions[0]["metadata"]["metrics"]["mae"] == 0.1
    assert Path(versions[0]["artifact_path"]).exists()


def test_activate_sets_current_alias() -> None:
    """activate() writes active metadata and current.joblib alias artifact."""
    model = LinearRegression().fit([[1], [2]], [2.0, 4.0])
    registry.save(model, "lr")
    active = registry.activate("lr")

    assert active["name"] == "lr"
    current_path = Path(active["current_alias_path"])
    assert current_path.exists()
    loaded = registry.get_active()
    assert loaded is not None
    assert loaded["name"] == "lr"
