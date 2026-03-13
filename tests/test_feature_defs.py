"""Tests for feature definition helpers."""

from __future__ import annotations

import pandas as pd

from features.feature_defs import _paydown_ratio, _rate_spread, _term_remaining_ratio


def test_performance_features_handle_missing_columns() -> None:
    df = pd.DataFrame({"current_actual_upb": [100000, 90000]})

    paydown = _paydown_ratio(df)
    spread = _rate_spread(df)
    term_ratio = _term_remaining_ratio(df)

    assert len(paydown) == 2
    assert len(spread) == 2
    assert len(term_ratio) == 2
    assert paydown.isna().all()
    assert spread.isna().all()
    assert term_ratio.isna().all()
