"""Macro indicator join: align FRED monthly features to a loan DataFrame.

Given a DataFrame with a date column (YYYYMM string or datetime-like), this
module looks up the corresponding macro indicators and appends them as new
columns.  All lookups are keyed on the calendar *month* of the observation,
so indicators are assumed to be available at the start of each month (FRED
values are forward-filled within the month prior to saving).

Usage
-----
    from features.macro_join import join_macro_features

    # Origination data — date column is YYYYMM (e.g. "200301")
    enriched = join_macro_features(df, date_col="first_payment_date")

    # Performance data — monthly_reporting_period is also YYYYMM
    enriched = join_macro_features(df, date_col="monthly_reporting_period")
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from utils.logging import log

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "fred.yaml"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_macro(cfg: dict | None = None) -> pd.DataFrame:
    """Load the FRED macro parquet and return it with a monthly PeriodIndex."""
    if cfg is None:
        with open(_CONFIG_PATH) as fh:
            cfg = yaml.safe_load(fh)

    raw_path = Path(cfg["output"]["raw_dir"]) / cfg["output"]["filename"]
    if not raw_path.exists():
        raise FileNotFoundError(
            f"FRED macro parquet not found at {raw_path}. "
            "Run:  python -m main ingest --source fred"
        )

    df = pd.read_parquet(raw_path)
    df.index = pd.PeriodIndex(df.index, freq="M")
    df.index.name = "period"
    return df


def _date_col_to_period_str(s: pd.Series) -> pd.Series:
    """Convert a date column to a Series of ``"YYYY-MM"`` strings.

    Supported input formats
    -----------------------
    * **YYYYMM** integer or string (Fannie Mae convention, e.g. ``200301`` or
      ``"200301"``).  These are six-character strings containing only digits.
    * **YYYYMMDD** eight-character digit strings (e.g. ``"20030115"``).
    * **ISO / datetime-like** strings or :class:`pandas.Timestamp` objects
      (e.g. ``"2003-01-15"``).

    Unresolvable values are returned as ``pd.NA``.
    """
    s_str = s.astype(str).str.strip()

    # YYYYMM (6 digits) — Fannie Mae first_payment_date / monthly_reporting_period
    if s_str.str.match(r"^\d{6}$").all():
        return s_str.str[:4] + "-" + s_str.str[4:6]

    # YYYYMMDD (8 digits)
    if s_str.str.match(r"^\d{8}$").all():
        return s_str.str[:4] + "-" + s_str.str[4:6]

    # General datetime parse → period string
    parsed = pd.to_datetime(s, errors="coerce")
    return parsed.dt.to_period("M").astype(str)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def join_macro_features(
    df: pd.DataFrame,
    date_col: str,
    *,
    macro_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Left-join FRED macro indicators onto ``df`` aligned to observation month.

    Each macro column is appended at the calendar month that matches
    ``date_col``.  Rows whose date cannot be resolved, or that fall outside
    the FRED time range, receive ``NaN`` in all macro columns.

    Args:
        df: Input DataFrame (loan-level or any observation-per-row frame).
        date_col: Name of the column containing the observation date (see
            supported formats in :func:`_date_col_to_period_str`).
        macro_df: Optional pre-loaded macro DataFrame (useful in tests or
            batch jobs that call this function many times).  When ``None`` the
            parquet is loaded from the path in ``config/fred.yaml``.

    Returns:
        A copy of ``df`` with macro indicator columns appended.

    Raises:
        KeyError: If ``date_col`` is not present in ``df``.
        FileNotFoundError: If the FRED macro parquet has not been generated
            yet (propagated from :func:`_load_macro`).
    """
    if date_col not in df.columns:
        raise KeyError(
            f"date_col '{date_col}' not found in DataFrame "
            f"(available columns: {list(df.columns)})"
        )

    if macro_df is None:
        macro_df = _load_macro()

    macro_cols = macro_df.columns.tolist()
    log.info(
        "Joining {} macro feature(s) onto {:,} rows via date_col='{}'",
        len(macro_cols),
        len(df),
        date_col,
    )

    # Build a plain-dict lookup: "YYYY-MM" → {col: value, ...}
    # Using a dict is faster than repeated DataFrame indexing for large frames.
    macro_index_str = macro_df.index.astype(str)
    macro_lookup: dict[str, dict[str, float]] = {
        period_str: macro_df.loc[period, :].to_dict()
        for period_str, period in zip(macro_index_str, macro_df.index)
    }

    period_str_series = _date_col_to_period_str(df[date_col])

    result = df.copy()
    for col in macro_cols:
        result[col] = period_str_series.map(
            lambda p, c=col: macro_lookup.get(p, {}).get(c)  # type: ignore[return-value]
        )

    null_rows = result[macro_cols].isna().any(axis=1).sum()
    if null_rows:
        log.warning(
            "{:,} row(s) have at least one null macro value "
            "(date out of FRED range or unparseable)",
            null_rows,
        )

    log.info("Macro join complete — added columns: {}", macro_cols)
    return result
