"""Tests for features/engineer.py — build_features."""
from __future__ import annotations

import pytest


def test_build_features_missing_source_raises() -> None:
    """build_features raises FileNotFoundError for an unknown source with no data."""
    from features.engineer import build_features

    with pytest.raises(FileNotFoundError):
        build_features("nonexistent-source-xyz")


def test_build_features_fannie_no_data_raises() -> None:
    """build_features raises FileNotFoundError when no Fannie origination parquets exist."""
    from unittest.mock import patch
    from pathlib import Path
    from features.engineer import build_features

    # Patch glob to return an empty list so no files appear to exist
    with patch.object(Path, "glob", return_value=[]):
        with pytest.raises(FileNotFoundError, match="origination"):
            build_features("fannie-mae")
