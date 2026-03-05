"""Data loading façade — routes source keys to concrete loaders."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils.logging import log

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------
# Add new sources here: key → callable that accepts (source_str) → DataFrame
# ---------------------------------------------------------------------------


def load(source: str) -> pd.DataFrame:
    """Load a dataset by source key and return a DataFrame.

    Supported source keys
    ---------------------
    ``fannie-mae``
        Trigger full Fannie Mae origination + performance ingestion from
        local files.  Returns the origination DataFrame (the larger
        performance dataset is written to parquet only).

    ``csv:<path>``
        Read a local CSV file directly.

    ``parquet:<path>``
        Read a local Parquet file directly.

    Args:
        source: Source key string.

    Returns:
        Loaded DataFrame.

    Raises:
        ValueError: If the source key is not recognised.
        FileNotFoundError: If a file-based source path does not exist.
    """
    log.info("loader.load called with source={}", source)

    if source == "fannie-mae":
        return _load_fannie_mae()

    if source == "fred":
        return _load_fred()

    if source.startswith("csv:"):
        return _load_csv(source[4:])

    if source.startswith("parquet:"):
        return _load_parquet(source[8:])

    raise ValueError(
        f"Unknown source key '{source}'. "
        "Supported: 'fannie-mae', 'fred', 'csv:<path>', 'parquet:<path>'"
    )


# ---------------------------------------------------------------------------
# Concrete loaders
# ---------------------------------------------------------------------------


def _load_fannie_mae() -> pd.DataFrame:
    """Run Fannie Mae ingestion and return the origination DataFrame."""
    from data_ingestion.ingest_fannie import ingest_all

    result = ingest_all()
    orig_paths = result["origination"]
    if not orig_paths:
        raise FileNotFoundError(
            "No Fannie Mae origination files were ingested. "
            "Check data/README.md for download instructions."
        )
    # Return first origination quarter as representative DataFrame
    df = pd.read_parquet(orig_paths[0])
    log.info("Returning origination frame: {} rows, {} cols", len(df), df.shape[1])
    return df


def _load_csv(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"CSV file not found: {p}")
    df = pd.read_csv(p)
    log.info("Loaded CSV {} ({} rows, {} cols)", p, len(df), df.shape[1])
    return df


def _load_fred() -> pd.DataFrame:
    """Run FRED ingestion and return the monthly macro DataFrame."""
    from data_ingestion.ingest_fred import ingest_fred

    df = ingest_fred()
    log.info("Loaded FRED macro data ({} rows, {} cols)", len(df), df.shape[1])
    return df


def _load_parquet(path: str) -> pd.DataFrame:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Parquet file not found: {p}")
    df = pd.read_parquet(p)
    log.info("Loaded parquet {} ({} rows, {} cols)", p, len(df), df.shape[1])
    return df
