"""
tests/test_labels.py
--------------------
Unit tests for features/labels.py using small synthetic DataFrames.

Each test exercises a distinct aspect of the labeling logic so that
failures pinpoint the exact broken invariant.
"""

import pandas as pd
import pytest

from features.labels import build_labels


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(records: list[tuple]) -> pd.DataFrame:
    """Build a minimal loan-month panel from (loan_id, reporting_month, dpd) tuples."""
    return pd.DataFrame(records, columns=["loan_id", "reporting_month", "dpd"])


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

class TestPositiveLabel:
    def test_bad_event_within_horizon(self):
        """Observation at month 0; bad event at month +6 → label=1."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2023-07-01", 65),
        ])
        result = build_labels(df)
        obs_row = result[result["reporting_month"] == "2023-01-01"]
        assert obs_row["label"].iloc[0] == 1

    def test_bad_event_at_horizon_boundary(self):
        """Bad event at exactly +12 months is included (inclusive upper bound)."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2024-01-01", 60),   # exactly 12 calendar months later
        ])
        result = build_labels(df)
        obs_row = result[result["reporting_month"] == "2023-01-01"]
        assert obs_row["label"].iloc[0] == 1

    def test_dpd_exactly_at_threshold(self):
        """DPD equal to the threshold counts as a bad event."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2023-04-01", 60),
        ])
        result = build_labels(df)
        obs_row = result[result["reporting_month"] == "2023-01-01"]
        assert obs_row["label"].iloc[0] == 1

    def test_label_row_that_is_itself_bad(self):
        """A row that is a bad event can also be an observation with label=1
        if there is another bad event within its own horizon."""
        df = _make_df([
            ("L1", "2023-01-01", 60),   # bad event, also an observation
            ("L1", "2023-06-01", 90),   # another bad event inside the horizon
        ])
        result = build_labels(df)
        jan_row = result[result["reporting_month"] == "2023-01-01"]
        # The Jan row's own DPD is not in its own forward window, but the Jun event is
        assert jan_row["label"].iloc[0] == 1


# ---------------------------------------------------------------------------
# Negative-label tests
# ---------------------------------------------------------------------------

class TestNegativeLabel:
    def test_no_bad_events_at_all(self):
        """No DPD ever hits threshold → all labels 0."""
        df = _make_df([
            ("L1", "2023-01-01", 30),
            ("L1", "2023-02-01", 45),
            ("L1", "2023-03-01", 59),
        ])
        result = build_labels(df)
        assert (result["label"] == 0).all()

    def test_bad_event_outside_horizon(self):
        """Bad event 13 months after observation (> 12-month horizon) → label=0."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2024-02-01", 90),   # 13 months later
        ])
        result = build_labels(df)
        obs_row = result[result["reporting_month"] == "2023-01-01"]
        assert obs_row["label"].iloc[0] == 0

    def test_bad_event_same_month_excluded(self):
        """An event on the exact observation date is not in the *forward* window."""
        df = _make_df([
            ("L1", "2023-01-01", 60),   # only row — its horizon contains no *future* events
        ])
        result = build_labels(df)
        assert result["label"].iloc[0] == 0

    def test_bad_event_before_observation(self):
        """Historical bad events (before the observation date) do not count."""
        df = _make_df([
            ("L1", "2022-06-01", 90),   # in the past
            ("L1", "2023-01-01", 0),    # observation row
        ])
        result = build_labels(df)
        obs_row = result[result["reporting_month"] == "2023-01-01"]
        assert obs_row["label"].iloc[0] == 0


# ---------------------------------------------------------------------------
# Multi-loan tests
# ---------------------------------------------------------------------------

class TestMultipleLoans:
    def test_loans_labeled_independently(self):
        """L1 goes bad; L2 does not. Labels must not bleed across loans."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2023-06-01", 65),
            ("L2", "2023-01-01", 0),
            ("L2", "2023-06-01", 30),   # L2 stays clean
        ])
        result = build_labels(df)
        l1_jan = result[(result["loan_id"] == "L1") & (result["reporting_month"] == "2023-01-01")]
        l2_jan = result[(result["loan_id"] == "L2") & (result["reporting_month"] == "2023-01-01")]
        assert l1_jan["label"].iloc[0] == 1
        assert l2_jan["label"].iloc[0] == 0

    def test_row_count_unchanged(self):
        """build_labels must return the same number of rows as the input."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2023-06-01", 65),
            ("L2", "2023-01-01", 0),
            ("L2", "2023-04-01", 30),
        ])
        result = build_labels(df)
        assert len(result) == len(df)


# ---------------------------------------------------------------------------
# Configurability tests
# ---------------------------------------------------------------------------

class TestConfigurableParameters:
    def test_shorter_horizon_excludes_late_event(self):
        """Event 7 months out is excluded by a 6-month horizon."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2023-08-01", 90),   # 7 months later
        ])
        result = build_labels(df, horizon_months=6)
        obs_row = result[result["reporting_month"] == "2023-01-01"]
        assert obs_row["label"].iloc[0] == 0

    def test_shorter_horizon_includes_near_event(self):
        """Event 6 months out is included by a 6-month horizon (boundary inclusive)."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2023-07-01", 90),   # 6 months later
        ])
        result = build_labels(df, horizon_months=6)
        obs_row = result[result["reporting_month"] == "2023-01-01"]
        assert obs_row["label"].iloc[0] == 1

    def test_custom_dpd_threshold(self):
        """Lower dpd_threshold triggers a positive label for a previously clean event."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2023-03-01", 30),
        ])
        result = build_labels(df, dpd_threshold=30)
        obs_row = result[result["reporting_month"] == "2023-01-01"]
        assert obs_row["label"].iloc[0] == 1

    def test_custom_column_names(self):
        """build_labels respects non-default column name parameters."""
        df = pd.DataFrame({
            "id":    ["A",        "A"],
            "month": ["2023-01-01", "2023-06-01"],
            "dpd_value": [0, 70],
        })
        result = build_labels(
            df,
            loan_id_col="id",
            date_col="month",
            dpd_col="dpd_value",
        )
        obs_row = result[result["month"] == "2023-01-01"]
        assert obs_row["label"].iloc[0] == 1


# ---------------------------------------------------------------------------
# Output contract tests
# ---------------------------------------------------------------------------

class TestOutputContract:
    def test_label_column_added(self):
        """Output must contain a 'label' column alongside all input columns."""
        df = _make_df([("L1", "2023-01-01", 30)])
        result = build_labels(df)
        assert "label" in result.columns
        assert {"loan_id", "reporting_month", "dpd"}.issubset(result.columns)

    def test_label_dtype_is_int(self):
        """Label column must be integer (0 or 1), not float."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2023-06-01", 65),
        ])
        result = build_labels(df)
        assert result["label"].dtype == int

    def test_label_values_binary(self):
        """Label column contains only 0 and 1."""
        df = _make_df([
            ("L1", "2023-01-01", 0),
            ("L1", "2023-06-01", 65),
            ("L2", "2023-01-01", 10),
        ])
        result = build_labels(df)
        assert set(result["label"].unique()).issubset({0, 1})

    def test_input_not_mutated(self):
        """build_labels must not modify the caller's DataFrame."""
        df = _make_df([("L1", "2023-01-01", 30)])
        original_cols = list(df.columns)
        _ = build_labels(df)
        assert list(df.columns) == original_cols
        assert "label" not in df.columns
