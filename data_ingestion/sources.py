"""Concrete dataset source implementations."""
from __future__ import annotations

from pathlib import Path

import pandas as pd


def from_csv(path: str | Path) -> pd.DataFrame:
    """Load a local CSV file."""
    return pd.read_csv(path)


def from_parquet(path: str | Path) -> pd.DataFrame:
    """Load a local Parquet file."""
    return pd.read_parquet(path)

# TODO: add from_fred(), from_url(), from_s3(), etc.
