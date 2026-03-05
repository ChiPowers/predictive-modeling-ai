"""Tests for MLflow integration in training.trainer."""
from __future__ import annotations

from pathlib import Path

import mlflow
import pytest

from models import registry


@pytest.fixture(autouse=True)
def _isolated_mlflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run every test against an isolated local MLflow store."""
    tracking_uri = tmp_path / "mlruns"
    tracking_uri.mkdir()
    mlflow.set_tracking_uri(str(tracking_uri))
    monkeypatch.setattr("config.settings.settings.mlflow_tracking_uri", str(tracking_uri))
    monkeypatch.setattr(registry, "_ARTIFACTS_DIR", tmp_path / "artifacts")


def test_train_model_returns_artifact_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """train_model returns the saved artifact path from the delegated trainer."""
    from training import trainer

    expected = Path("/tmp/prophet.joblib")
    monkeypatch.setattr(trainer, "_train_prophet", lambda mlflow_run=None: expected)

    out = trainer.train_model("prophet")
    assert out == expected


def test_run_is_logged_to_experiment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A training call creates a run in the requested experiment."""
    from training import trainer

    monkeypatch.setattr(trainer, "_train_prophet", lambda mlflow_run=None: Path("prophet.joblib"))
    experiment_name = "test-experiment"
    trainer.train_model("prophet", experiment_name=experiment_name)

    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name(experiment_name)
    assert experiment is not None
    runs = client.search_runs(experiment_ids=[experiment.experiment_id])
    assert len(runs) == 1


def test_run_name_is_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """The MLflow run name respects the provided run_name argument."""
    from training import trainer

    monkeypatch.setattr(trainer, "_train_prophet", lambda mlflow_run=None: Path("prophet.joblib"))
    trainer.train_model("prophet", run_name="my-custom-run")

    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name("predictive-modeling-ai")
    assert experiment is not None
    runs = client.search_runs(experiment_ids=[experiment.experiment_id])
    assert len(runs) == 1
    assert runs[0].info.run_name == "my-custom-run"


def test_params_logged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Core trainer configuration params are logged to MLflow."""
    from training import trainer

    monkeypatch.setattr(trainer, "_train_prophet", lambda mlflow_run=None: Path("prophet.joblib"))
    trainer.train_model("prophet")

    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name("predictive-modeling-ai")
    assert experiment is not None
    run = client.search_runs(experiment_ids=[experiment.experiment_id])[0]

    assert run.data.params["model"] == "prophet"
    assert "random_seed" in run.data.params
    assert "test_split" in run.data.params
    assert "forecast_horizon" in run.data.params


def test_unknown_model_raises_value_error() -> None:
    """Unsupported model keys raise ValueError."""
    from training.trainer import train_model

    with pytest.raises(ValueError, match="Unknown model key"):
        train_model("nonexistent-model")
