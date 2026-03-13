"""
features/labels.py
------------------
Construct binary 60+ DPD labels for each (loan, observation_month) row.

Definition
~~~~~~~~~~
For each row, the *observation date* is the value in ``date_col``.
The forward-looking window is the half-open interval::

    (observation_date, observation_date + horizon_months]

Label = 1 when the loan ever records ``dpd >= dpd_threshold`` inside that window.
Events on the observation date itself are excluded (the future hasn't happened yet).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml

log = logging.getLogger(__name__)

_DEFAULT_CONFIG = Path("config/labeling.yaml")


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def load_config(config_path: str | Path = _DEFAULT_CONFIG) -> dict[str, Any]:
    """Load and return the labeling YAML configuration as a plain dict."""
    path = Path(config_path)
    with path.open() as fh:
        return cast(dict[str, Any], yaml.safe_load(fh))


# ---------------------------------------------------------------------------
# Core labeling logic
# ---------------------------------------------------------------------------


def build_labels(
    df: pd.DataFrame,
    loan_id_col: str = "loan_id",
    date_col: str = "reporting_month",
    dpd_col: str = "dpd",
    horizon_months: int = 12,
    dpd_threshold: int = 60,
) -> pd.DataFrame:
    """Attach a binary ``label`` column to a loan-month panel.

    For every row the *observation date* is the value already present in
    ``date_col``; no separate column is added.  The label is 1 when the
    same loan records ``dpd >= dpd_threshold`` in the window
    ``(observation_date, observation_date + horizon_months]``.

    Parameters
    ----------
    df:
        Raw loan-month panel – one row per loan per calendar month.
    loan_id_col:
        Column that uniquely identifies each loan.
    date_col:
        Column holding the monthly reporting / observation date.
    dpd_col:
        Column holding the Days Past Due value for that month.
    horizon_months:
        Number of calendar months to look forward (inclusive upper bound).
    dpd_threshold:
        DPD value that, if reached or exceeded, constitutes a bad event.

    Returns
    -------
    pandas.DataFrame
        A copy of *df* with an extra integer ``label`` column (0 or 1).
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])

    # Isolate rows that are already a "bad" event
    bad = df.loc[df[dpd_col] >= dpd_threshold, [loan_id_col, date_col]].rename(
        columns={date_col: "_event_date"}
    )

    if bad.empty:
        df["label"] = 0
        log.info("No bad events found; all %d labels set to 0.", len(df))
        return df

    # Join each observation row to all bad events of the same loan
    obs = df[[loan_id_col, date_col]].merge(bad, on=loan_id_col)

    # Compute the inclusive horizon end for each observation
    obs["_horizon_end"] = obs[date_col] + pd.DateOffset(months=horizon_months)

    # Keep only bad events strictly after the observation date and within horizon
    in_window = (obs["_event_date"] > obs[date_col]) & (obs["_event_date"] <= obs["_horizon_end"])

    flagged = obs.loc[in_window, [loan_id_col, date_col]].drop_duplicates().assign(label=1)

    result = df.merge(flagged, on=[loan_id_col, date_col], how="left")
    result["label"] = result["label"].fillna(0).astype(int)

    n_pos = result["label"].sum()
    n_total = len(result)
    log.info(
        "Labeled %d / %d observations positive (%.1f%%).",
        n_pos,
        n_total,
        100.0 * n_pos / n_total if n_total else 0.0,
    )
    return result


# ---------------------------------------------------------------------------
# End-to-end pipeline entry point
# ---------------------------------------------------------------------------


def label_dataset(
    input_path: str | Path,
    config_path: str | Path = _DEFAULT_CONFIG,
    output_path: str | Path | None = None,
) -> pd.DataFrame:
    """Load raw data, build labels, and persist the labeled artifact.

    Parameters
    ----------
    input_path:
        Path to the raw loan-month panel.  Parquet and CSV are supported;
        the format is inferred from the file extension.
    config_path:
        Path to ``config/labeling.yaml``.
    output_path:
        Destination for the labeled parquet file.  Defaults to
        ``output_path`` from the config (``data/processed/labeled.parquet``).

    Returns
    -------
    pandas.DataFrame
        The labeled DataFrame (also written to *output_path*).
    """
    cfg = load_config(config_path)

    input_path = Path(input_path)
    if input_path.suffix.lower() == ".csv":
        df = pd.read_csv(input_path)
    else:
        df = pd.read_parquet(input_path)

    log.info("Loaded %d rows from %s.", len(df), input_path)

    labeled = build_labels(
        df,
        loan_id_col=cfg.get("loan_id_col", "loan_id"),
        date_col=cfg.get("date_col", "reporting_month"),
        dpd_col=cfg.get("dpd_col", "dpd"),
        horizon_months=int(cfg.get("horizon_months", 12)),
        dpd_threshold=int(cfg.get("dpd_threshold", 60)),
    )

    dest = Path(output_path or cfg.get("output_path", "data/processed/labeled.parquet"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    labeled.to_parquet(dest, index=False)

    log.info("Labeled dataset saved to %s (%d rows).", dest, len(labeled))
    return labeled
