"""Tests for features."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest


def test_build_features_delegates_to_pipeline(monkeypatch: pytest.MonkeyPatch) -> None:
    """features.engineer.build_features delegates to build_features.run()."""
    from features import engineer

    expected = pd.DataFrame({"x": [1, 2, 3]})

    def fake_run(source: str, groups: Any = None) -> pd.DataFrame:
        assert source == "fannie-mae"
        assert groups is None
        return expected

    monkeypatch.setattr(engineer, "run_feature_pipeline", fake_run)
    out = engineer.build_features("fannie-mae")
    assert out.equals(expected)
