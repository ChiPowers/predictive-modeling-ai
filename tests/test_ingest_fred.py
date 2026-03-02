"""Tests for data_ingestion/ingest_fred.py."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# _to_monthly
# ---------------------------------------------------------------------------


def test_to_monthly_mean_weekly() -> None:
    """Weekly series should be averaged to monthly means."""
    from data_ingestion.ingest_fred import _to_monthly

    dates = pd.date_range("2020-01-01", periods=8, freq="W")
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    s = pd.Series(values, index=dates, name="TEST")

    result = _to_monthly(s, "mean")

    assert isinstance(result.index, pd.PeriodIndex)
    assert result.index.freqstr == "M"
    # All values must be finite floats
    assert result.notna().all()


def test_to_monthly_ffill_quarterly() -> None:
    """Quarterly series should be forward-filled to monthly."""
    from data_ingestion.ingest_fred import _to_monthly

    dates = pd.to_datetime(["2020-01-01", "2020-04-01", "2020-07-01", "2020-10-01"])
    s = pd.Series([100.0, 101.0, 102.0, 103.0], index=dates, name="GDPC1")

    result = _to_monthly(s, "ffill")

    assert isinstance(result.index, pd.PeriodIndex)
    assert result.index.freqstr == "M"
    # ffill only extends to the last observed date (Oct), so 10 months (Jan–Oct)
    assert len(result) == 10
    # Jan, Feb, Mar should all hold the Q1 value (100.0)
    assert result[pd.Period("2020-01", "M")] == 100.0
    assert result[pd.Period("2020-02", "M")] == 100.0
    assert result[pd.Period("2020-03", "M")] == 100.0
    # Apr should hold Q2 value (101.0)
    assert result[pd.Period("2020-04", "M")] == 101.0


def test_to_monthly_unknown_method_raises() -> None:
    from data_ingestion.ingest_fred import _to_monthly

    s = pd.Series([1.0], index=pd.to_datetime(["2020-01-01"]))
    with pytest.raises(ValueError, match="Unknown resample_method"):
        _to_monthly(s, "unknown")


# ---------------------------------------------------------------------------
# ingest_fred — cached path (no network)
# ---------------------------------------------------------------------------


def test_ingest_fred_returns_cached_parquet(tmp_path: Path) -> None:
    """When the parquet already exists and overwrite=False, no HTTP call is made."""
    from data_ingestion.ingest_fred import ingest_fred

    # Build a tiny mock macro parquet
    periods = pd.period_range("2020-01", periods=3, freq="M")
    macro = pd.DataFrame(
        {"fed_funds_rate": [1.5, 1.5, 1.5]},
        index=periods.astype(str),
    )
    macro.index.name = "period"

    raw_dir = tmp_path / "data" / "raw" / "fred"
    raw_dir.mkdir(parents=True)
    parquet_path = raw_dir / "macro_monthly.parquet"
    macro.to_parquet(parquet_path, index=True, engine="pyarrow")

    fake_cfg = {
        "output": {"raw_dir": str(raw_dir), "filename": "macro_monthly.parquet"},
    }

    with patch("data_ingestion.ingest_fred._load_config", return_value=fake_cfg), patch("httpx.Client") as mock_client:
        result = ingest_fred(overwrite=False)

    # httpx should never have been called
    mock_client.assert_not_called()

    assert isinstance(result.index, pd.PeriodIndex)
    assert "fed_funds_rate" in result.columns
    assert len(result) == 3


# ---------------------------------------------------------------------------
# _fetch_series_csv — unit-level HTTP mock
# ---------------------------------------------------------------------------


def test_fetch_series_csv_parses_response() -> None:
    """_fetch_series_csv should parse a FRED CSV response into a dated Series."""
    from data_ingestion.ingest_fred import _fetch_series_csv

    csv_body = "DATE,FEDFUNDS\n2020-01-01,1.55\n2020-02-01,1.58\n2020-03-01,0.65\n"

    fake_response = MagicMock()
    fake_response.text = csv_body
    fake_response.raise_for_status = MagicMock()

    fake_cfg = {
        "csv_fallback": {
            "base_url": "https://fred.stlouisfed.org/graph/fredgraph.csv",
            "timeout_seconds": 10,
        }
    }

    with patch("httpx.Client") as mock_client_cls:
        mock_client_cls.return_value.__enter__.return_value.get.return_value = fake_response
        result = _fetch_series_csv("FEDFUNDS", fake_cfg)

    assert len(result) == 3
    assert result.iloc[0] == pytest.approx(1.55)
    assert result.name == "FEDFUNDS"
    assert isinstance(result.index, pd.DatetimeIndex)
