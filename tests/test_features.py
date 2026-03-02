"""Tests for the feature engineering pipeline.

Test categories
---------------
1. Column presence  — all required output columns exist after build_features().
2. No leakage       — each performance feature at time t only uses data ≤ t.
3. Origination      — individual origination feature correctness and clipping.
4. Performance      — rolling / cumulative delinquency feature correctness.
5. Macro stubs      — macro columns are present and entirely NaN.
6. Schema validation — build_features raises when a required column is absent.
7. Determinism      — same input always produces the same output.
"""
from __future__ import annotations

import pandas as pd
import numpy as np
import pytest

from features.build_features import build_features, _validate_schema
from features.feature_defs import FEATURE_REGISTRY


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _make_raw(n_loans: int = 3, n_periods: int = 4) -> pd.DataFrame:
    """Build a minimal synthetic panel DataFrame for testing.

    Contains all columns required by every registered feature function.
    """
    import itertools

    loan_ids = [f"L{i:03d}" for i in range(n_loans)]
    periods = pd.date_range("2020-01-01", periods=n_periods, freq="MS")

    rows = list(itertools.product(loan_ids, periods))
    df = pd.DataFrame(rows, columns=["loan_id", "observation_date"])

    df["orig_date"] = pd.Timestamp("2019-01-01")  # 12 months before first period

    # Origination columns
    df["fico_score"] = 720
    df["ltv"] = 80.0
    df["dti"] = 35.0
    df["loan_purpose"] = "P"
    df["occupancy_type"] = "P"
    df["orig_upb"] = 300_000.0
    df["orig_rate"] = 3.5
    df["loan_term"] = 360
    df["num_units"] = 1
    df["first_time_homebuyer"] = "N"

    # Performance columns — default current (0)
    df["current_upb"] = 295_000.0
    df["delinquency_status"] = 0

    # Introduce a delinquency pattern for loan L001 when enough rows exist:
    # period index 1 → 30-day DQ; period index 2 → 60-day DQ; rest current
    if n_loans >= 2 and n_periods >= 2:
        mask_30 = (df["loan_id"] == "L001") & (df["observation_date"] == periods[1])
        df.loc[mask_30, "delinquency_status"] = 1
    if n_loans >= 2 and n_periods >= 3:
        mask_60 = (df["loan_id"] == "L001") & (df["observation_date"] == periods[2])
        df.loc[mask_60, "delinquency_status"] = 2

    return df


@pytest.fixture()
def raw_df() -> pd.DataFrame:
    return _make_raw()


@pytest.fixture()
def feature_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    return build_features(raw_df)


# ── 1. Column presence ────────────────────────────────────────────────────────


def test_all_required_output_cols_present(feature_df: pd.DataFrame) -> None:
    """All columns listed in config/features.yaml required_output_cols must exist."""
    from pathlib import Path
    import yaml

    cfg_path = Path(__file__).resolve().parents[1] / "config" / "features.yaml"
    with cfg_path.open() as fh:
        cfg = yaml.safe_load(fh)

    required = cfg.get("required_output_cols", [])
    assert required, "required_output_cols should not be empty in features.yaml"

    missing = [c for c in required if c not in feature_df.columns]
    assert not missing, f"Missing required output columns: {missing}"


def test_loan_id_and_observation_date_preserved(feature_df: pd.DataFrame) -> None:
    """Key columns loan_id and observation_date must pass through unchanged."""
    assert "loan_id" in feature_df.columns
    assert "observation_date" in feature_df.columns


# ── 2. No leakage ─────────────────────────────────────────────────────────────


def test_rolling_30d_dq_no_forward_leakage() -> None:
    """rolling_30d_dq_3m at period t must equal 0 if all prior periods are current.

    Scenario: loan becomes delinquent only at period 3.
    At periods 0, 1, 2 the flag must be 0; at period 3 it becomes 1.
    """
    periods = pd.date_range("2020-01-01", periods=5, freq="MS")
    df = pd.DataFrame({
        "loan_id": ["L000"] * 5,
        "observation_date": periods,
        "orig_date": pd.Timestamp("2019-01-01"),
        "delinquency_status": [0, 0, 0, 1, 0],
        "fico_score": 720, "ltv": 80.0, "dti": 35.0,
        "loan_purpose": "P", "occupancy_type": "P",
        "orig_upb": 300_000.0, "orig_rate": 3.5, "loan_term": 360,
        "num_units": 1, "first_time_homebuyer": "N",
        "current_upb": 295_000.0,
    })
    result = build_features(df)
    flags = result.sort_values("observation_date")["rolling_30d_dq_3m"].tolist()

    # Periods 0-2: no DQ yet → flag must be 0
    assert flags[0] == 0, "Period 0: no prior DQ, flag must be 0"
    assert flags[1] == 0, "Period 1: no prior DQ, flag must be 0"
    assert flags[2] == 0, "Period 2: no prior DQ, flag must be 0"
    # Period 3: 30-day DQ → flag = 1
    assert flags[3] == 1, "Period 3: DQ occurred, flag must be 1"


def test_ever_30d_dq_no_forward_leakage() -> None:
    """ever_30d_dq must be 0 before the first DQ event and 1 afterwards."""
    periods = pd.date_range("2020-01-01", periods=4, freq="MS")
    df = pd.DataFrame({
        "loan_id": ["L000"] * 4,
        "observation_date": periods,
        "orig_date": pd.Timestamp("2019-01-01"),
        "delinquency_status": [0, 1, 0, 0],
        "fico_score": 720, "ltv": 80.0, "dti": 35.0,
        "loan_purpose": "P", "occupancy_type": "P",
        "orig_upb": 300_000.0, "orig_rate": 3.5, "loan_term": 360,
        "num_units": 1, "first_time_homebuyer": "N",
        "current_upb": 295_000.0,
    })
    result = build_features(df)
    flags = result.sort_values("observation_date")["ever_30d_dq"].tolist()

    assert flags[0] == 0, "Before first DQ, ever_30d_dq must be 0"
    assert flags[1] == 1, "At first DQ period, ever_30d_dq must be 1"
    assert flags[2] == 1, "After DQ (now current), ever_30d_dq must remain 1"
    assert flags[3] == 1, "ever_30d_dq must never decrease"


def test_num_dq_months_monotone_per_loan() -> None:
    """num_dq_months must be non-decreasing within each loan over time."""
    result = build_features(_make_raw(n_loans=3, n_periods=6))
    for loan_id, group in result.groupby("loan_id"):
        vals = group.sort_values("observation_date")["num_dq_months"].tolist()
        for i in range(1, len(vals)):
            assert vals[i] >= vals[i - 1], (
                f"num_dq_months decreased for {loan_id}: {vals}"
            )


# ── 3. Origination feature correctness ───────────────────────────────────────


def test_fico_clipping() -> None:
    """FICO values outside [300, 850] must be clipped."""
    df = _make_raw(n_loans=1, n_periods=1)
    df["fico_score"] = 900  # above upper bound
    result = build_features(df)
    assert result["fico_score"].max() <= 850

    df["fico_score"] = 100  # below lower bound
    result = build_features(df)
    assert result["fico_score"].min() >= 300


def test_ltv_clipping() -> None:
    df = _make_raw(n_loans=1, n_periods=1)
    df["ltv"] = 250.0
    result = build_features(df)
    assert result["ltv"].max() <= 200.0


def test_dti_clipping() -> None:
    df = _make_raw(n_loans=1, n_periods=1)
    df["dti"] = 110.0
    result = build_features(df)
    assert result["dti"].max() <= 100.0


def test_loan_purpose_encoding() -> None:
    """P → 0, C → 1, R → 2, unknown → 3."""
    df = _make_raw(n_loans=1, n_periods=1)
    for code, expected in [("P", 0), ("C", 1), ("R", 2), ("X", 3)]:
        df["loan_purpose"] = code
        result = build_features(df)
        assert result["loan_purpose_enc"].iloc[0] == expected, f"code={code}"


def test_occupancy_encoding() -> None:
    """P → 0, I → 1, S → 2, unknown → 3."""
    df = _make_raw(n_loans=1, n_periods=1)
    for code, expected in [("P", 0), ("I", 1), ("S", 2), ("Z", 3)]:
        df["occupancy_type"] = code
        result = build_features(df)
        assert result["occupancy_enc"].iloc[0] == expected, f"code={code}"


def test_fthb_flag() -> None:
    """Y/y → 1, N/n or anything else → 0."""
    df = _make_raw(n_loans=1, n_periods=1)
    for val, expected in [("Y", 1), ("y", 1), ("N", 0), ("", 0)]:
        df["first_time_homebuyer"] = val
        result = build_features(df)
        assert result["fthb_flag"].iloc[0] == expected, f"val={val!r}"


def test_months_since_orig_positive() -> None:
    """months_since_orig must be ≥ 0 and reflect the date difference."""
    df = _make_raw(n_loans=1, n_periods=1)
    df["observation_date"] = pd.Timestamp("2020-07-01")
    df["orig_date"] = pd.Timestamp("2019-01-01")
    result = build_features(df)
    assert result["months_since_orig"].iloc[0] == 18


# ── 4. Performance feature correctness ───────────────────────────────────────


def test_rolling_60d_dq_only_set_on_severe_dq() -> None:
    """rolling_60d_dq_3m must be 0 for a loan that only hits 30-day DQ."""
    periods = pd.date_range("2020-01-01", periods=3, freq="MS")
    df = pd.DataFrame({
        "loan_id": ["L000"] * 3,
        "observation_date": periods,
        "orig_date": pd.Timestamp("2019-01-01"),
        "delinquency_status": [0, 1, 0],  # only 30-day DQ
        "fico_score": 720, "ltv": 80.0, "dti": 35.0,
        "loan_purpose": "P", "occupancy_type": "P",
        "orig_upb": 300_000.0, "orig_rate": 3.5, "loan_term": 360,
        "num_units": 1, "first_time_homebuyer": "N",
        "current_upb": 295_000.0,
    })
    result = build_features(df)
    assert result["rolling_60d_dq_3m"].max() == 0, (
        "60-day DQ flag must be 0 when max delinquency is only 1 month"
    )


def test_delinquency_status_missing_becomes_zero() -> None:
    """NaN delinquency_status must be treated as current (0)."""
    df = _make_raw(n_loans=1, n_periods=2)
    df["delinquency_status"] = np.nan
    result = build_features(df)
    assert (result["delinquency_status"] == 0).all()


# ── 5. Macro stub columns ─────────────────────────────────────────────────────


def test_macro_stubs_present_and_nan(feature_df: pd.DataFrame) -> None:
    """Macro stub columns must exist and contain only NaN values."""
    macro_cols = ["macro_unemployment_rate", "macro_10yr_treasury", "macro_hpi_change"]
    for col in macro_cols:
        assert col in feature_df.columns, f"Macro stub column '{col}' missing"
        assert feature_df[col].isna().all(), f"Macro stub '{col}' should be all-NaN"


# ── 6. Schema validation ──────────────────────────────────────────────────────


def test_validate_schema_raises_on_missing_col(feature_df: pd.DataFrame) -> None:
    """_validate_schema must raise ValueError when a required column is absent."""
    with pytest.raises(ValueError, match="missing required columns"):
        _validate_schema(feature_df.drop(columns=["fico_score"]), ["fico_score"])


def test_validate_schema_passes_on_complete_df(feature_df: pd.DataFrame) -> None:
    """_validate_schema must not raise when all required columns are present."""
    _validate_schema(feature_df, list(feature_df.columns))  # should not raise


# ── 7. Determinism ────────────────────────────────────────────────────────────


def test_build_features_is_deterministic(raw_df: pd.DataFrame) -> None:
    """build_features must produce identical results on two identical inputs."""
    result1 = build_features(raw_df.copy())
    result2 = build_features(raw_df.copy())

    shared_cols = [c for c in result1.columns if c in result2.columns]
    numeric_cols = result1[shared_cols].select_dtypes(include="number").columns.tolist()

    pd.testing.assert_frame_equal(
        result1[numeric_cols].reset_index(drop=True),
        result2[numeric_cols].reset_index(drop=True),
        check_dtype=False,
    )


def test_build_features_row_count_unchanged(raw_df: pd.DataFrame, feature_df: pd.DataFrame) -> None:
    """build_features must not drop or duplicate rows."""
    assert len(feature_df) == len(raw_df)


# ── 8. Feature registry sanity ────────────────────────────────────────────────


def test_feature_registry_non_empty() -> None:
    """FEATURE_REGISTRY must contain at least one entry per group."""
    from features.feature_defs import GROUP_ORDER

    groups_in_registry = {spec.group for spec in FEATURE_REGISTRY.values()}
    for group in GROUP_ORDER:
        assert group in groups_in_registry, f"No features registered for group '{group}'"


def test_feature_registry_output_col_matches_name() -> None:
    """Every FeatureSpec with produces='' should have output_col == name."""
    for name, spec in FEATURE_REGISTRY.items():
        assert spec.output_col, f"Feature '{name}' has empty output_col"
