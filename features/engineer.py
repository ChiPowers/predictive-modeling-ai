"""Feature engineering pipeline."""
from __future__ import annotations

import pandas as pd

from utils.logging import log


def build_features(source: str) -> pd.DataFrame:
    """Transform raw data for ``source`` into model-ready features.

    Reads from ``data/raw/<source>.parquet`` and writes to
    ``data/processed/<source>_features.parquet``.

    Args:
        source: Dataset source key (must already be ingested).

    Returns:
        Feature DataFrame.
    """
    log.info("build_features called for source={}", source)
    # TODO: implement lag features, rolling statistics, calendar features, etc.
    raise NotImplementedError("Feature engineering not yet implemented")
