"""Time-based train / val / test split.

Rows are sorted by ``date_col`` and then partitioned at month boundaries so
that no future information leaks into earlier splits.  The cut-points are
derived from the *sorted* index rather than calendar math, which keeps the
split sizes close to the requested ratios even for unevenly distributed data.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from utils.logging import log


@dataclass
class SplitResult:
    train: pd.DataFrame
    val: pd.DataFrame
    test: pd.DataFrame

    # Inclusive boundary months (Period[M]) for each split
    train_end: pd.Period
    val_end: pd.Period
    test_end: pd.Period


def split_by_time(
    df: pd.DataFrame,
    date_col: str,
    train_ratio: float = 0.6,
    val_ratio: float = 0.2,
    test_ratio: float = 0.2,
) -> SplitResult:
    """Split *df* by observation month, preserving temporal order.

    Parameters
    ----------
    df:
        Input DataFrame.  Must contain *date_col*.
    date_col:
        Column whose values are coercible to ``datetime64``.
    train_ratio, val_ratio, test_ratio:
        Approximate fraction of rows in each split.  Must sum to 1.

    Returns
    -------
    SplitResult
        Named tuple of (train, val, test) DataFrames plus the last month
        included in each split.
    """
    if abs(train_ratio + val_ratio + test_ratio - 1.0) > 1e-6:
        raise ValueError("train_ratio + val_ratio + test_ratio must equal 1.0")

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col).reset_index(drop=True)

    # Assign a month period to every row
    months: pd.Series = df[date_col].dt.to_period("M")
    sorted_months = months.sort_values().unique()  # ordered unique months

    n_months = len(sorted_months)
    if n_months < 3:
        raise ValueError(
            f"Need at least 3 distinct months to produce train/val/test splits; "
            f"found {n_months}."
        )

    train_cut = max(1, round(n_months * train_ratio))
    val_cut = max(train_cut + 1, round(n_months * (train_ratio + val_ratio)))
    # Clamp so test always has at least one month
    val_cut = min(val_cut, n_months - 1)

    train_end_month = sorted_months[train_cut - 1]
    val_end_month = sorted_months[val_cut - 1]
    test_end_month = sorted_months[-1]

    train_mask = months <= train_end_month
    val_mask = (months > train_end_month) & (months <= val_end_month)
    test_mask = months > val_end_month

    train_df = df[train_mask].reset_index(drop=True)
    val_df = df[val_mask].reset_index(drop=True)
    test_df = df[test_mask].reset_index(drop=True)

    log.info(
        "Split sizes — train: {} ({} months, up to {}), "
        "val: {} ({} months, up to {}), "
        "test: {} ({} months, up to {})",
        len(train_df),
        train_cut,
        train_end_month,
        len(val_df),
        val_cut - train_cut,
        val_end_month,
        len(test_df),
        n_months - val_cut,
        test_end_month,
    )

    return SplitResult(
        train=train_df,
        val=val_df,
        test=test_df,
        train_end=train_end_month,
        val_end=val_end_month,
        test_end=test_end_month,
    )
