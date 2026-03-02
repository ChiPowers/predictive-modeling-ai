"""Feature engineering pipeline — CLI entry point.

Delegates all logic to ``features.build_features``.
"""
from __future__ import annotations

import pandas as pd

from features.build_features import build_features as _build_features
from features.build_features import run as _run
from utils.logging import log


def build_features(source: str) -> pd.DataFrame:
    """Transform raw data for *source* into model-ready features.

    Reads from ``data/raw/<source>.parquet`` and writes to
    ``data/processed/features.parquet``.

    Args:
        source: Dataset source key (must already be ingested).

    Returns:
        Feature DataFrame.
    """
    log.info("build_features called for source={}", source)
    return _run(source)
