"""Tests for MLflow tracking integration in training.trainer."""
from __future__ import annotations

from pathlib import Path

import mlflow
import pytest
from sklearn.dummy import DummyRegressor

from models import registry


@pytest.fixture(autouse=True)
def _isolated_mlflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test against a fresh in-process MLflow store."""
    tracking_uri = tmp_path / "mlruns"
    tracking_uri.mkdir()
    mlflow.set_tracking_uri(str(tracking_uri))
    monkeypatch.setattr("config.settings.settings.mlflow_tracking_uri", str(tracking_uri))
    monkeypatch.setattr(registry, "_ARTIFACTS_DIR", tmp_path / "artifacts")


# ---------------------------------------------------------------------------
# Core behaviour
# ---------------------------------------------------------------------------


def test_train_model_returns_run_id() -> None:
    """train_model returns a non-empty string run_id."""
    from training.trainer import train_model

    run_id = train_model("dummy")
    assert isinstance(run_id, str)
    assert len(run_id) > 0


def test_run_is_logged_to_experiment() -> None:
    """Run appears in the MLflow experiment after training."""
    from training.trainer import train_model

    experiment_name = "test-experiment"
    run_id = train_model("dummy", experiment_name=experiment_name)

    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name(experiment_name)
    assert experiment is not None

    runs = client.search_runs(experiment_ids=[experiment.experiment_id])
    assert any(r.info.run_id == run_id for r in runs)


def test_run_name_is_set() -> None:
    """The MLflow run carries the name passed via --run-name."""
    from training.trainer import train_model

    run_id = train_model("dummy", run_name="my-custom-run")

    client = mlflow.tracking.MlflowClient()
    run = client.get_run(run_id)
    assert run.info.run_name == "my-custom-run"


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


def test_params_logged() -> None:
    """Expected params are present in the completed run."""
    from training.trainer import train_model

    run_id = train_model("dummy")
    client = mlflow.tracking.MlflowClient()
    run = client.get_run(run_id)

    assert run.data.params["model"] == "dummy"
    assert "random_seed" in run.data.params
    assert "test_split" in run.data.params
    assert "forecast_horizon" in run.data.params


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def test_metrics_logged() -> None:
    """mae and rmse metrics are present and finite."""
    import math

    from training.trainer import train_model

    run_id = train_model("dummy")
    client = mlflow.tracking.MlflowClient()
    run = client.get_run(run_id)

    assert "mae" in run.data.metrics
    assert "rmse" in run.data.metrics
    assert math.isfinite(run.data.metrics["mae"])
    assert math.isfinite(run.data.metrics["rmse"])
    assert run.data.metrics["mae"] >= 0
    assert run.data.metrics["rmse"] >= 0


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def test_model_registered_in_registry() -> None:
    """train_model registers a new version in the MLflow Model Registry."""
    from config.settings import settings
    from training.trainer import train_model

    train_model("dummy")
    client = mlflow.tracking.MlflowClient()
    versions = client.search_model_versions(
        f"name='{settings.mlflow_registered_model_name}'"
    )
    assert len(versions) >= 1
    assert versions[0].name == settings.mlflow_registered_model_name


# ---------------------------------------------------------------------------
# Local joblib registry
# ---------------------------------------------------------------------------


def test_local_joblib_artifact_saved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """train_model also persists a .joblib file via models.registry.save."""
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setattr(registry, "_ARTIFACTS_DIR", artifacts_dir)

    from training.trainer import train_model

    run_id = train_model("dummy")

    saved = list(artifacts_dir.glob("dummy-*.joblib"))
    assert len(saved) == 1
    # filename embeds the first 8 chars of the run_id
    assert run_id[:8] in saved[0].stem


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_unknown_model_raises_value_error() -> None:
    """Requesting an unsupported model raises ValueError before any MLflow call."""
    from training.trainer import train_model

    with pytest.raises(ValueError, match="Unknown model"):
        train_model("nonexistent-model")
