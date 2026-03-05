"""Tests for performance-summary merging inside feature engineering."""
from __future__ import annotations

import pandas as pd

from features.build_features import _merge_perf_summary


def test_merge_perf_summary_coerces_object_perf_columns() -> None:
    orig = pd.DataFrame({"loan_sequence_number": ["L1"]})
    perf = pd.DataFrame({
        "loan_sequence_number": ["L1", "L1", "L1"],
        "loan_age": ["0", "1", None],
        "current_actual_upb": ["300000", "299500", "299000"],
        "current_delinquency_status": ["0", "1", None],
    })

    _merge_perf_summary(orig, perf)

    assert float(orig.loc[0, "max_loan_age"]) == 1.0
    assert float(orig.loc[0, "latest_upb"]) == 299000.0
    assert float(orig.loc[0, "max_dpd"]) == 1.0

