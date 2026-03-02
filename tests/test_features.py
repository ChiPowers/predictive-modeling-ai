"""Tests for features."""
from __future__ import annotations

import pytest


def test_build_features_raises_not_implemented() -> None:
    """Feature engineering must raise NotImplementedError until implemented."""
    from features.engineer import build_features

    with pytest.raises(NotImplementedError):
        build_features("test-source")
