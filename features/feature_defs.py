"""Feature registry: named feature functions organised by group.

Each feature function has the signature::

    fn(df: pd.DataFrame) -> pd.Series

The returned Series must be named with the feature's output column name.
The pipeline in ``build_features.py`` calls them in group order
(origination → performance → macro_stub) and assigns each result as a new
column on the working DataFrame, so later functions can depend on earlier ones.

Registration
------------
Use the ``@register`` decorator::

    @register("my_feature", group="origination",
              required=["raw_col"], produces=["my_feature"])
    def feat_my_feature(df: pd.DataFrame) -> pd.Series:
        return pd.to_numeric(df["raw_col"], errors="coerce")
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

# Type alias for a feature function
FeatureFn = Callable[[pd.DataFrame], pd.Series]

# Execution order for groups
GROUP_ORDER: list[str] = ["origination", "performance", "macro_stub"]


@dataclass
class FeatureSpec:
    """Metadata for a single feature."""

    name: str
    fn: FeatureFn
    group: str
    required_input_cols: list[str] = field(default_factory=list)
    output_col: str = ""

    def __post_init__(self) -> None:
        if not self.output_col:
            self.output_col = self.name


# Global feature registry: feature_name → FeatureSpec
FEATURE_REGISTRY: dict[str, FeatureSpec] = {}


def register(
    name: str,
    *,
    group: str,
    required: list[str],
    produces: str = "",
) -> Callable[[FeatureFn], FeatureFn]:
    """Decorator that registers a feature function in FEATURE_REGISTRY."""

    def decorator(fn: FeatureFn) -> FeatureFn:
        FEATURE_REGISTRY[name] = FeatureSpec(
            name=name,
            fn=fn,
            group=group,
            required_input_cols=required,
            output_col=produces or name,
        )
        return fn

    return decorator


# ── Origination Features ────────────────────────────────────────────────────
# Static attributes captured at loan origination.
# These features clean / validate the raw values and encode categoricals.


@register("fico_score", group="origination", required=["fico_score"])
def feat_fico_score(df: pd.DataFrame) -> pd.Series:
    """FICO credit score at origination, clipped to [300, 850]."""
    return pd.to_numeric(df["fico_score"], errors="coerce").clip(300, 850).rename("fico_score")


@register("ltv", group="origination", required=["ltv"])
def feat_ltv(df: pd.DataFrame) -> pd.Series:
    """Loan-to-value ratio at origination (%), clipped to [0, 200]."""
    return pd.to_numeric(df["ltv"], errors="coerce").clip(0, 200).rename("ltv")


@register("dti", group="origination", required=["dti"])
def feat_dti(df: pd.DataFrame) -> pd.Series:
    """Debt-to-income ratio (%), clipped to [0, 100]."""
    return pd.to_numeric(df["dti"], errors="coerce").clip(0, 100).rename("dti")


@register("loan_purpose_enc", group="origination", required=["loan_purpose"], produces="loan_purpose_enc")
def feat_loan_purpose_enc(df: pd.DataFrame) -> pd.Series:
    """Encode loan purpose: P=0 (purchase), C=1 (cash-out refi), R=2 (rate/term refi), else 3."""
    _MAP = {"P": 0, "C": 1, "R": 2}
    return (
        df["loan_purpose"].astype(str).str.upper().map(_MAP).fillna(3).astype(np.int8).rename("loan_purpose_enc")
    )


@register("occupancy_enc", group="origination", required=["occupancy_type"], produces="occupancy_enc")
def feat_occupancy_enc(df: pd.DataFrame) -> pd.Series:
    """Encode occupancy type: P=0 (primary), I=1 (investment), S=2 (second home), else 3."""
    _MAP = {"P": 0, "I": 1, "S": 2}
    return (
        df["occupancy_type"].astype(str).str.upper().map(_MAP).fillna(3).astype(np.int8).rename("occupancy_enc")
    )


@register("orig_upb", group="origination", required=["orig_upb"])
def feat_orig_upb(df: pd.DataFrame) -> pd.Series:
    """Original unpaid principal balance (non-negative)."""
    return pd.to_numeric(df["orig_upb"], errors="coerce").clip(lower=0).rename("orig_upb")


@register("orig_rate", group="origination", required=["orig_rate"])
def feat_orig_rate(df: pd.DataFrame) -> pd.Series:
    """Note rate at origination (%), clipped to [0, 30]."""
    return pd.to_numeric(df["orig_rate"], errors="coerce").clip(0, 30).rename("orig_rate")


@register("loan_term", group="origination", required=["loan_term"])
def feat_loan_term(df: pd.DataFrame) -> pd.Series:
    """Amortization term in months (e.g. 360, 180), non-negative."""
    return pd.to_numeric(df["loan_term"], errors="coerce").clip(lower=0).rename("loan_term")


@register("num_units", group="origination", required=["num_units"])
def feat_num_units(df: pd.DataFrame) -> pd.Series:
    """Number of units in the property, clipped to [1, 4]."""
    return pd.to_numeric(df["num_units"], errors="coerce").clip(1, 4).astype(np.int8).rename("num_units")


@register("fthb_flag", group="origination", required=["first_time_homebuyer"], produces="fthb_flag")
def feat_fthb_flag(df: pd.DataFrame) -> pd.Series:
    """First-time homebuyer flag: Y/y → 1, all other values → 0."""
    return df["first_time_homebuyer"].astype(str).str.upper().eq("Y").astype(np.int8).rename("fthb_flag")


# ── Performance Features ────────────────────────────────────────────────────
# Time-varying attributes computed as of each observation_date.
# LEAKAGE GUARD: all rolling/cumulative operations work on data sorted by
# (loan_id, observation_date) and only look back in time (never forward).
# The pipeline sorts the DataFrame once before running this group.


@register(
    "months_since_orig",
    group="performance",
    required=["observation_date", "orig_date"],
    produces="months_since_orig",
)
def feat_months_since_orig(df: pd.DataFrame) -> pd.Series:
    """Age of loan in whole months: observation_date − orig_date, floored at 0."""
    obs = pd.to_datetime(df["observation_date"])
    orig = pd.to_datetime(df["orig_date"])
    delta = (obs.dt.year - orig.dt.year) * 12 + (obs.dt.month - orig.dt.month)
    return delta.clip(lower=0).astype(np.int16).rename("months_since_orig")


@register("current_upb", group="performance", required=["current_upb"])
def feat_current_upb(df: pd.DataFrame) -> pd.Series:
    """Current unpaid principal balance at observation_date (non-negative)."""
    return pd.to_numeric(df["current_upb"], errors="coerce").clip(lower=0).rename("current_upb")


@register("delinquency_status", group="performance", required=["delinquency_status"])
def feat_delinquency_status(df: pd.DataFrame) -> pd.Series:
    """Months delinquent at observation_date; 0 = current. Missing → 0."""
    return (
        pd.to_numeric(df["delinquency_status"], errors="coerce")
        .fillna(0)
        .clip(lower=0)
        .astype(np.int8)
        .rename("delinquency_status")
    )


@register(
    "rolling_30d_dq_3m",
    group="performance",
    required=["loan_id", "observation_date", "delinquency_status"],
    produces="rolling_30d_dq_3m",
)
def feat_rolling_30d_dq_3m(df: pd.DataFrame) -> pd.Series:
    """Flag (0/1): any 30+ day delinquency in the trailing 3 months.

    Uses only history up to and including observation_date (no leakage).
    DataFrame must already be sorted by (loan_id, observation_date).
    """
    dlq = pd.to_numeric(df["delinquency_status"], errors="coerce").fillna(0)
    flag = (dlq >= 1).astype(int)
    result = (
        df.assign(_flag=flag)
        .groupby("loan_id", sort=False)["_flag"]
        .transform(lambda s: s.rolling(3, min_periods=1).max())
        .astype(np.int8)
    )
    return result.rename("rolling_30d_dq_3m")


@register(
    "rolling_60d_dq_3m",
    group="performance",
    required=["loan_id", "observation_date", "delinquency_status"],
    produces="rolling_60d_dq_3m",
)
def feat_rolling_60d_dq_3m(df: pd.DataFrame) -> pd.Series:
    """Flag (0/1): any 60+ day delinquency in the trailing 3 months.

    Uses only history up to and including observation_date (no leakage).
    """
    dlq = pd.to_numeric(df["delinquency_status"], errors="coerce").fillna(0)
    flag = (dlq >= 2).astype(int)
    result = (
        df.assign(_flag=flag)
        .groupby("loan_id", sort=False)["_flag"]
        .transform(lambda s: s.rolling(3, min_periods=1).max())
        .astype(np.int8)
    )
    return result.rename("rolling_60d_dq_3m")


@register(
    "ever_30d_dq",
    group="performance",
    required=["loan_id", "observation_date", "delinquency_status"],
    produces="ever_30d_dq",
)
def feat_ever_30d_dq(df: pd.DataFrame) -> pd.Series:
    """Flag (0/1): loan has EVER been 30+ DQ as of observation_date (cumulative max)."""
    dlq = pd.to_numeric(df["delinquency_status"], errors="coerce").fillna(0)
    flag = (dlq >= 1).astype(int)
    result = (
        df.assign(_flag=flag)
        .groupby("loan_id", sort=False)["_flag"]
        .transform("cummax")
        .astype(np.int8)
    )
    return result.rename("ever_30d_dq")


@register(
    "ever_60d_dq",
    group="performance",
    required=["loan_id", "observation_date", "delinquency_status"],
    produces="ever_60d_dq",
)
def feat_ever_60d_dq(df: pd.DataFrame) -> pd.Series:
    """Flag (0/1): loan has EVER been 60+ DQ as of observation_date."""
    dlq = pd.to_numeric(df["delinquency_status"], errors="coerce").fillna(0)
    flag = (dlq >= 2).astype(int)
    result = (
        df.assign(_flag=flag)
        .groupby("loan_id", sort=False)["_flag"]
        .transform("cummax")
        .astype(np.int8)
    )
    return result.rename("ever_60d_dq")


@register(
    "num_dq_months",
    group="performance",
    required=["loan_id", "observation_date", "delinquency_status"],
    produces="num_dq_months",
)
def feat_num_dq_months(df: pd.DataFrame) -> pd.Series:
    """Cumulative count of months with any delinquency as of observation_date."""
    dlq = pd.to_numeric(df["delinquency_status"], errors="coerce").fillna(0)
    flag = (dlq >= 1).astype(int)
    result = (
        df.assign(_flag=flag)
        .groupby("loan_id", sort=False)["_flag"]
        .transform("cumsum")
        .astype(np.int16)
    )
    return result.rename("num_dq_months")


# ── Macro Stub Features ─────────────────────────────────────────────────────
# Placeholder columns that will be populated via a macro data join in Task 4.
# They are intentionally NaN so that downstream models can be developed before
# the macro data pipeline is complete.


@register("macro_unemployment_rate", group="macro_stub", required=[], produces="macro_unemployment_rate")
def feat_macro_unemployment_rate(df: pd.DataFrame) -> pd.Series:
    """Macro: unemployment rate — stub (NaN). Will be joined in Task 4."""
    return pd.Series(np.nan, index=df.index, name="macro_unemployment_rate", dtype=np.float64)


@register("macro_10yr_treasury", group="macro_stub", required=[], produces="macro_10yr_treasury")
def feat_macro_10yr_treasury(df: pd.DataFrame) -> pd.Series:
    """Macro: 10-year treasury rate — stub (NaN). Will be joined in Task 4."""
    return pd.Series(np.nan, index=df.index, name="macro_10yr_treasury", dtype=np.float64)


@register("macro_hpi_change", group="macro_stub", required=[], produces="macro_hpi_change")
def feat_macro_hpi_change(df: pd.DataFrame) -> pd.Series:
    """Macro: HPI year-over-year change — stub (NaN). Will be joined in Task 4."""
    return pd.Series(np.nan, index=df.index, name="macro_hpi_change", dtype=np.float64)
