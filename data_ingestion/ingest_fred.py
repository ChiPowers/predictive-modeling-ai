"""FRED (Federal Reserve Economic Data) macro indicator ingestion.

Pulls economic time series from the St. Louis Fed and stores them as a single
monthly-frequency parquet for downstream feature engineering.

Authentication
--------------
Set ``FRED_API_KEY`` in your ``.env`` file or environment.
If the key is absent the ingester falls back to FRED's public CSV download
endpoint (no registration required, but local resampling is used instead of
server-side aggregation).

Usage (CLI)
-----------
    python -m main ingest --source fred

Usage (programmatic)
--------------------
    from data_ingestion.ingest_fred import ingest_fred
    df = ingest_fred()                  # use cached parquet if present
    df = ingest_fred(overwrite=True)    # re-download all series
"""
from __future__ import annotations

import io
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import httpx
import pandas as pd
import yaml

from utils.logging import log

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "fred.yaml"


def _load_config() -> dict[str, Any]:
    with open(_CONFIG_PATH) as fh:
        return cast(dict[str, Any], yaml.safe_load(fh))


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------


def _fetch_series_api(series_id: str, api_key: str, cfg: dict[str, Any]) -> pd.Series:
    """Fetch a FRED series via the authenticated JSON API.

    Returns a DatetimeIndex-indexed Series of float values.  FRED missing-value
    sentinels (``"."``) are coerced to ``NaN``.
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": cfg["api"]["file_type"],
        "observation_start": cfg["api"]["observation_start"],
    }
    url = cfg["api"]["base_url"]
    timeout = cfg["api"]["timeout_seconds"]

    log.debug("FRED API → {}", series_id)
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, params=params)
        response.raise_for_status()

    observations = response.json()["observations"]
    dates = [obs["date"] for obs in observations]
    raw_values = [obs["value"] for obs in observations]

    s = pd.Series(raw_values, index=pd.to_datetime(dates), name=series_id, dtype=object)
    s = s.replace(".", pd.NA)
    return pd.to_numeric(s, errors="coerce")


def _fetch_series_csv(series_id: str, cfg: dict[str, Any]) -> pd.Series:
    """Fetch a FRED series from the public CSV endpoint (no API key required).

    Returns a DatetimeIndex-indexed Series of float values.
    """
    base = cfg["csv_fallback"]["base_url"]
    timeout = cfg["csv_fallback"]["timeout_seconds"]
    url = f"{base}?id={series_id}"

    log.debug("FRED CSV → {}", series_id)
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()

    raw_df = pd.read_csv(io.StringIO(response.text), parse_dates=["DATE"])
    raw_df.columns = [c.strip() for c in raw_df.columns]

    # The value column name equals the series ID (or a variant); take the non-DATE column.
    value_col = next(c for c in raw_df.columns if c != "DATE")
    return pd.Series(
        pd.to_numeric(raw_df[value_col], errors="coerce").to_numpy(),
        index=raw_df["DATE"],
        name=series_id,
    )


# ---------------------------------------------------------------------------
# Resampling
# ---------------------------------------------------------------------------


def _to_monthly(s: pd.Series, resample_method: str) -> pd.Series:
    """Resample a DatetimeIndex Series to a monthly PeriodIndex Series.

    Args:
        s: DatetimeIndex-indexed numeric Series (any native frequency).
        resample_method: ``"mean"`` averages observations within each month;
            ``"ffill"`` forward-fills the last known value (e.g. quarterly GDP).

    Returns:
        Series with a :class:`pandas.PeriodIndex` at monthly (``"M"``) frequency.
    """
    if resample_method == "mean":
        monthly = s.resample("MS").mean()
    elif resample_method == "ffill":
        monthly = s.resample("MS").ffill()
    else:
        raise ValueError(
            f"Unknown resample_method '{resample_method}'. Expected 'mean' or 'ffill'."
        )
    monthly.index = monthly.index.to_period("M")
    return monthly


# ---------------------------------------------------------------------------
# Fetcher factory (avoids lambda / E731)
# ---------------------------------------------------------------------------


def _make_api_fetcher(api_key: str, cfg: dict[str, Any]) -> Callable[[str], pd.Series]:
    def _fetch(series_id: str) -> pd.Series:
        return _fetch_series_api(series_id, api_key, cfg)

    return _fetch


def _make_csv_fetcher(cfg: dict[str, Any]) -> Callable[[str], pd.Series]:
    def _fetch(series_id: str) -> pd.Series:
        return _fetch_series_csv(series_id, cfg)

    return _fetch


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ingest_fred(
    *,
    overwrite: bool = False,
    api_key: str | None = None,
) -> pd.DataFrame:
    """Fetch configured FRED series and save as a monthly parquet.

    Resolves the API key from (in order of priority):
    1. The ``api_key`` argument.
    2. The ``FRED_API_KEY`` environment variable / ``.env`` file via
       :attr:`config.settings.Settings.fred_api_key`.

    When no key is available the public CSV endpoint is used instead.

    Args:
        overwrite: Re-download and overwrite an existing parquet when ``True``.
            When ``False`` and the parquet already exists, the cached file is
            returned immediately without any network requests.
        api_key: Optional explicit API key; takes priority over settings.

    Returns:
        DataFrame with one row per calendar month and one column per configured
        series.  The index is a :class:`pandas.PeriodIndex` at monthly frequency
        with name ``"period"``.

    Raises:
        RuntimeError: If every configured series fails to fetch.
    """
    from config.settings import settings

    cfg = _load_config()
    out_dir = Path(cfg["output"]["raw_dir"])
    out_path = out_dir / cfg["output"]["filename"]
    out_dir.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and not overwrite:
        log.info(
            "FRED parquet already exists at {} — returning cached data "
            "(pass overwrite=True to refresh)",
            out_path,
        )
        df = pd.read_parquet(out_path)
        df.index = pd.PeriodIndex(df.index, freq="M")
        df.index.name = "period"
        return df

    # Resolve API key
    resolved_key: str | None = api_key or getattr(settings, "fred_api_key", None)

    if resolved_key:
        log.info("FRED API key found — using authenticated JSON API")
        fetcher = _make_api_fetcher(resolved_key, cfg)
    else:
        log.warning(
            "FRED_API_KEY not set — falling back to public CSV endpoint. "
            "Set FRED_API_KEY in your .env for full API access."
        )
        fetcher = _make_csv_fetcher(cfg)

    series_config: list[dict[str, Any]] = cfg["series"]
    monthly_frames: list[pd.Series] = []

    for sc in series_config:
        sid: str = sc["id"]
        name: str = sc["name"]
        resample: str = sc["resample_method"]

        log.info("Fetching FRED series {} → column '{}'", sid, name)
        try:
            raw = fetcher(sid)
            monthly = _to_monthly(raw, resample)
            monthly.name = name
            monthly_frames.append(monthly)
        except Exception as exc:
            log.error("Failed to fetch FRED series {}: {}", sid, exc)
            # Partial failure: skip this series and continue

    if not monthly_frames:
        raise RuntimeError(
            "No FRED series could be fetched. "
            "Check network access and config/fred.yaml."
        )

    macro_df = pd.concat(monthly_frames, axis=1)
    macro_df.index.name = "period"

    # Serialise index as string for parquet compatibility across pandas versions
    save_df = macro_df.copy()
    save_df.index = save_df.index.astype(str)
    save_df.to_parquet(out_path, index=True, engine="pyarrow")

    log.info(
        "FRED macro parquet written → {} ({:,} months × {} series)",
        out_path,
        len(macro_df),
        macro_df.shape[1],
    )
    return macro_df
