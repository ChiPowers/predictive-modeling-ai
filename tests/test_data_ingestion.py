"""Tests for data_ingestion."""
from __future__ import annotations

import pytest


def test_load_unknown_source_raises_value_error() -> None:
    """Loader raises ValueError for unrecognised source keys."""
    from data_ingestion.loader import load

    with pytest.raises(ValueError, match="Unknown source key"):
        load("unknown-source")


def test_from_csv(tmp_path) -> None:
    """from_csv should return a non-empty DataFrame."""
    import pandas as pd
    from data_ingestion.sources import from_csv

    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("date,value\n2024-01-01,100\n2024-01-02,110\n")

    df = from_csv(csv_file)

    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert list(df.columns) == ["date", "value"]
