"""Tests for training/interpretability.py."""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("shap", reason="shap not installed")

from sklearn.datasets import make_classification  # noqa: E402
from sklearn.ensemble import GradientBoostingClassifier  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fitted_tree_model(n: int = 200, p: int = 8, seed: int = 0) -> tuple[Any, Any, Any]:
    X, y = make_classification(n_samples=n, n_features=p, random_state=seed)
    model = GradientBoostingClassifier(n_estimators=20, random_state=seed)
    model.fit(X, y)
    return model, X, y


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_explain_returns_feature_importance_dict(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from training.interpretability import explain

    model, X, _ = _fitted_tree_model()
    feature_names = [f"feat_{i}" for i in range(X.shape[1])]

    result = explain(model, X[:50], X[50:], feature_names=feature_names, max_display=5)

    assert isinstance(result, dict)
    assert set(result.keys()) == set(feature_names)
    assert all(v >= 0 for v in result.values()), "Mean |SHAP| must be non-negative"


def test_explain_saves_figures(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from training.interpretability import explain

    model, X, _ = _fitted_tree_model()

    explain(model, X[:50], X[50:], max_display=4)

    assert (tmp_path / "reports" / "figures" / "shap_summary.png").exists()
    assert (tmp_path / "reports" / "figures" / "shap_bar.png").exists()


def test_explain_infers_feature_names_from_dataframe(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    import pandas as pd  # noqa: PLC0415

    from training.interpretability import explain

    model, X, _ = _fitted_tree_model()
    cols = [f"col_{i}" for i in range(X.shape[1])]
    df = pd.DataFrame(X, columns=cols)

    result = explain(model, df.iloc[:50], df.iloc[50:], max_display=4)

    assert set(result.keys()) == set(cols)
