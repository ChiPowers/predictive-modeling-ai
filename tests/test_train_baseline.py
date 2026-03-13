"""Tests for training/train_baseline.py."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from training.train_baseline import _evaluate, run

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def features_parquet(tmp_path: Path) -> Path:
    rng = np.random.default_rng(7)
    n = 730  # ~2 years daily
    dates = pd.date_range("2022-01-01", periods=n, freq="D")
    X = rng.normal(size=(n, 3))
    logits = 0.9 * X[:, 0] - 0.5 * X[:, 1] + rng.normal(scale=0.3, size=n)
    y = (logits > 0).astype(int)
    df = pd.DataFrame(
        {
            "date": dates,
            "feature_1": X[:, 0],
            "feature_2": X[:, 1],
            "feature_3": X[:, 2],
            "target": y,
        }
    )
    path = tmp_path / "features.parquet"
    df.to_parquet(path, index=False)
    return path


@pytest.fixture()
def features_csv(tmp_path: Path, features_parquet: Path) -> Path:
    df = pd.read_parquet(features_parquet)
    path = tmp_path / "features.csv"
    df.to_csv(path, index=False)
    return path


CONFIG_PATH = Path(__file__).parent.parent / "config" / "training.yaml"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_run_returns_metrics_dict(features_parquet, tmp_path):
    metrics = run(features_parquet, CONFIG_PATH)
    assert isinstance(metrics, dict)
    for split in ("train", "val", "test"):
        assert split in metrics
        assert "auc_roc" in metrics[split]
        assert "brier_score" in metrics[split]
        assert "best_f1" in metrics[split]


def test_auc_above_chance(features_parquet):
    metrics = run(features_parquet, CONFIG_PATH)
    # Synthetic data has a strong signal; all splits should beat 0.7
    for split in ("train", "val", "test"):
        assert (
            metrics[split]["auc_roc"] > 0.70
        ), f"{split} AUC {metrics[split]['auc_roc']:.4f} not above 0.70"


def test_brier_below_naive(features_parquet):
    """Brier score should be lower than the naive always-predict-prevalence baseline."""
    metrics = run(features_parquet, CONFIG_PATH)
    for split in ("train", "val", "test"):
        prevalence = metrics[split]["positive_rate"]
        naive_brier = prevalence * (1 - prevalence)
        assert (
            metrics[split]["brier_score"] < naive_brier
        ), f"{split} Brier {metrics[split]['brier_score']:.4f} not below naive {naive_brier:.4f}"


def test_metrics_saved_to_reports(features_parquet):
    run(features_parquet, CONFIG_PATH)
    report_path = Path(__file__).parent.parent / "reports" / "baseline_metrics.json"
    assert report_path.exists()
    with open(report_path) as fh:
        saved = json.load(fh)
    assert "model" in saved
    assert "split_boundaries" in saved


def test_model_artifact_saved(features_parquet):
    metrics = run(features_parquet, CONFIG_PATH)
    assert Path(metrics["artifact_path"]).exists()


def test_csv_input_accepted(features_csv):
    metrics = run(features_csv, CONFIG_PATH)
    assert metrics["train"]["auc_roc"] > 0.0


def test_split_boundaries_in_output(features_parquet):
    metrics = run(features_parquet, CONFIG_PATH)
    boundaries = metrics["split_boundaries"]
    assert "train_end" in boundaries
    assert "val_end" in boundaries
    assert "test_end" in boundaries


def test_evaluate_returns_required_keys(features_parquet):
    """_evaluate must always return the expected metric keys."""
    import pandas as pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    rng = np.random.default_rng(1)
    X = pd.DataFrame(rng.normal(size=(200, 2)), columns=["a", "b"])
    y = pd.Series(rng.integers(0, 2, size=200))

    pipe = Pipeline([("sc", StandardScaler()), ("clf", LogisticRegression(max_iter=200))])
    pipe.fit(X, y)

    result = _evaluate(pipe, X, y, "test")
    for key in (
        "auc_roc",
        "average_precision",
        "brier_score",
        "best_f1",
        "best_precision",
        "best_recall",
        "best_threshold",
        "n_samples",
        "positive_rate",
    ):
        assert key in result, f"Missing key: {key}"
