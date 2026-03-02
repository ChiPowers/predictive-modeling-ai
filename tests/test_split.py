"""Tests for training/split.py."""

import numpy as np
import pandas as pd
import pytest

from training.split import SplitResult, split_by_time


def _make_df(n_days: int = 365 * 3, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2021-01-01", periods=n_days, freq="D")
    return pd.DataFrame(
        {"date": dates, "x": rng.normal(size=n_days), "y": rng.integers(0, 2, size=n_days)}
    )


def test_returns_split_result():
    df = _make_df()
    result = split_by_time(df, "date")
    assert isinstance(result, SplitResult)


def test_no_overlap():
    df = _make_df()
    r = split_by_time(df, "date")
    assert r.train["date"].max() < r.val["date"].min()
    assert r.val["date"].max() < r.test["date"].min()


def test_covers_all_rows():
    df = _make_df()
    r = split_by_time(df, "date")
    assert len(r.train) + len(r.val) + len(r.test) == len(df)


def test_approximate_ratios():
    df = _make_df(n_days=365 * 5)
    r = split_by_time(df, "date", train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)
    n = len(df)
    # Allow ±5% tolerance because cuts snap to month boundaries
    assert abs(len(r.train) / n - 0.60) < 0.05
    assert abs(len(r.val) / n - 0.20) < 0.05
    assert abs(len(r.test) / n - 0.20) < 0.05


def test_temporal_order_preserved():
    """Rows within each split must be in ascending date order."""
    df = _make_df()
    r = split_by_time(df, "date")
    for split_df in (r.train, r.val, r.test):
        assert split_df["date"].is_monotonic_increasing


def test_string_dates_accepted():
    df = _make_df()
    df["date"] = df["date"].astype(str)
    r = split_by_time(df, "date")
    assert len(r.train) > 0


def test_custom_ratios():
    df = _make_df()
    r = split_by_time(df, "date", train_ratio=0.7, val_ratio=0.15, test_ratio=0.15)
    assert len(r.train) > len(r.val)
    assert len(r.train) > len(r.test)


def test_insufficient_months_raises():
    dates = pd.date_range("2021-01-15", periods=45, freq="D")  # only 2 months
    df = pd.DataFrame({"date": dates, "y": 0})
    with pytest.raises(ValueError, match="at least 3 distinct months"):
        split_by_time(df, "date")


def test_ratios_must_sum_to_one():
    df = _make_df()
    with pytest.raises(ValueError, match="must equal 1.0"):
        split_by_time(df, "date", train_ratio=0.5, val_ratio=0.3, test_ratio=0.3)
