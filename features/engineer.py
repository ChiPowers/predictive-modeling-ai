"""CLI-facing feature engineering delegate.

The heavy lifting lives in :mod:`features.build_features`; this module keeps
the call site in ``main.py`` simple and stable.
"""
from __future__ import annotations

import pandas as pd

from features.build_features import run as run_feature_pipeline
from utils.logging import log


def build_features(source: str, groups: list[str] | None = None) -> pd.DataFrame:
    """Build and persist model features for a source key.

    Args:
        source: Dataset source key (currently ``"fannie-mae"``).

    Returns:
        Feature DataFrame.
    """
    log.info("Delegating feature build to features.build_features.run for source={}", source)
    return run_feature_pipeline(source, groups=groups)
