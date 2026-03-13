"""Tests for features/macro_join.py."""

from __future__ import annotations

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# _date_col_to_period_str
# ---------------------------------------------------------------------------


def test_date_col_yyyymm_string() -> None:
    """YYYYMM 6-digit strings (Fannie Mae format) should convert to YYYY-MM."""
    from features.macro_join import _date_col_to_period_str

    s = pd.Series(["200301", "200302", "200312"])
    result = _date_col_to_period_str(s)

    assert list(result) == ["2003-01", "2003-02", "2003-12"]


def test_date_col_yyyymm_integer() -> None:
    """YYYYMM integers cast to string should still parse correctly."""
    from features.macro_join import _date_col_to_period_str

    s = pd.Series([200301, 200302]).astype(str)
    result = _date_col_to_period_str(s)

    assert list(result) == ["2003-01", "2003-02"]


def test_date_col_yyyymmdd() -> None:
    """8-digit YYYYMMDD strings should yield the year-month portion."""
    from features.macro_join import _date_col_to_period_str

    s = pd.Series(["20030115", "20031231"])
    result = _date_col_to_period_str(s)

    assert list(result) == ["2003-01", "2003-12"]


def test_date_col_iso_dates() -> None:
    """ISO date strings should parse to YYYY-MM period strings."""
    from features.macro_join import _date_col_to_period_str

    s = pd.Series(["2020-03-15", "2021-11-01"])
    result = _date_col_to_period_str(s)

    assert list(result) == ["2020-03", "2021-11"]


# ---------------------------------------------------------------------------
# join_macro_features
# ---------------------------------------------------------------------------


def _make_macro_df() -> pd.DataFrame:
    """Build a small mock macro DataFrame with a PeriodIndex."""
    periods = pd.period_range("2020-01", periods=6, freq="M")
    df = pd.DataFrame(
        {
            "fed_funds_rate": [1.5, 1.5, 0.25, 0.25, 0.25, 0.10],
            "unemployment_rate": [3.5, 3.6, 4.4, 14.7, 13.3, 11.1],
        },
        index=periods,
    )
    df.index = df.index.astype(str)  # mirror parquet serialisation
    df.index = pd.PeriodIndex(df.index, freq="M")
    df.index.name = "period"
    return df


def test_join_macro_adds_columns() -> None:
    """Macro columns should be appended to the input DataFrame."""
    from features.macro_join import join_macro_features

    loans = pd.DataFrame(
        {
            "loan_id": [1, 2, 3],
            "first_payment_date": ["202001", "202003", "202005"],
        }
    )
    macro = _make_macro_df()
    result = join_macro_features(loans, date_col="first_payment_date", macro_df=macro)

    assert "fed_funds_rate" in result.columns
    assert "unemployment_rate" in result.columns
    assert len(result) == 3


def test_join_macro_correct_values() -> None:
    """Joined macro values should match the period of each loan."""
    from features.macro_join import join_macro_features

    loans = pd.DataFrame({"date": ["202001", "202004"]})
    macro = _make_macro_df()
    result = join_macro_features(loans, date_col="date", macro_df=macro)

    assert result.loc[0, "fed_funds_rate"] == pytest.approx(1.5)
    assert result.loc[1, "unemployment_rate"] == pytest.approx(14.7)


def test_join_macro_out_of_range_is_nan() -> None:
    """Dates outside the FRED range should produce NaN, not raise."""
    from features.macro_join import join_macro_features

    loans = pd.DataFrame({"date": ["199901"]})  # before macro_df range
    macro = _make_macro_df()
    result = join_macro_features(loans, date_col="date", macro_df=macro)

    assert pd.isna(result.loc[0, "fed_funds_rate"])


def test_join_macro_missing_date_col_raises() -> None:
    """KeyError is raised when date_col is not in the DataFrame."""
    from features.macro_join import join_macro_features

    loans = pd.DataFrame({"loan_id": [1, 2]})
    macro = _make_macro_df()

    with pytest.raises(KeyError, match="date_col"):
        join_macro_features(loans, date_col="nonexistent", macro_df=macro)


def test_join_macro_preserves_existing_columns() -> None:
    """Original DataFrame columns must not be modified or dropped."""
    from features.macro_join import join_macro_features

    loans = pd.DataFrame(
        {
            "loan_id": [10, 20],
            "orig_ltv": [80.0, 75.0],
            "first_payment_date": ["202002", "202003"],
        }
    )
    macro = _make_macro_df()
    result = join_macro_features(loans, date_col="first_payment_date", macro_df=macro)

    assert list(result["loan_id"]) == [10, 20]
    assert list(result["orig_ltv"]) == [80.0, 75.0]
