"""Feature definition registry.

Usage
-----
    from features.feature_defs import REGISTRY, FeatureSpec

    # All registered feature specs grouped by group name:
    for spec in REGISTRY["origination"]:
        print(spec.name, spec.dtype)

Each @register-decorated function receives a DataFrame and returns a Series
(for a single derived column) or a DataFrame (for multiple columns at once).
The pipeline in build_features.py calls them in registration order.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Registry infrastructure
# ---------------------------------------------------------------------------

FeatureFn = Callable[[pd.DataFrame], pd.Series | pd.DataFrame]


@dataclass
class FeatureSpec:
    name: str
    group: str
    fn: FeatureFn
    dtype: str = "float64"
    description: str = ""


REGISTRY: dict[str, list[FeatureSpec]] = {}


def register(
    group: str, name: str, dtype: str = "float64", description: str = ""
) -> Callable[[FeatureFn], FeatureFn]:
    """Decorator to register a feature function.

    Args:
        group:       Feature group (e.g. ``'origination'``).
        name:        Output column name(s).  For multi-column functions, pass
                     the shared prefix; the fn returns a DataFrame.
        dtype:       pandas dtype for the output (used for documentation).
        description: Human-readable description.
    """

    def decorator(fn: FeatureFn) -> FeatureFn:
        spec = FeatureSpec(name=name, group=group, fn=fn, dtype=dtype, description=description)
        REGISTRY.setdefault(group, []).append(spec)
        return fn

    return decorator


# ---------------------------------------------------------------------------
# ── Origination features ────────────────────────────────────────────────────
# ---------------------------------------------------------------------------

_LOG_UPB_CLIP = (9.0, 14.0)  # ln(~$8k) to ln(~$1.2M)


@register("origination", "log_upb", description="Natural log of original UPB")
def _log_upb(df: pd.DataFrame) -> pd.Series:
    upb = pd.to_numeric(df["orig_upb"], errors="coerce").clip(lower=1)
    return upb.apply(math.log).clip(*_LOG_UPB_CLIP).rename("log_upb")


@register(
    "origination",
    "is_first_time_homebuyer",
    dtype="bool",
    description="1 if first-time homebuyer, 0 otherwise (9 = unknown → NaN)",
)
def _is_fthb(df: pd.DataFrame) -> pd.Series:
    col = df["first_time_homebuyer_flag"].astype(str).str.upper().str.strip()
    return col.map({"Y": 1.0, "N": 0.0}).rename("is_first_time_homebuyer")


@register(
    "origination",
    "is_high_ltv",
    dtype="bool",
    description="1 when orig_ltv > 80 (PMI / default-risk threshold)",
)
def _is_high_ltv(df: pd.DataFrame) -> pd.Series:
    ltv = pd.to_numeric(df["orig_ltv"], errors="coerce")
    return (ltv > 80).astype(float).rename("is_high_ltv")


@register(
    "origination",
    "is_high_dti",
    dtype="bool",
    description="1 when orig_dti > 43 (CFPB qualified-mortgage threshold)",
)
def _is_high_dti(df: pd.DataFrame) -> pd.Series:
    dti = pd.to_numeric(df["orig_dti"], errors="coerce")
    return (dti > 43).astype(float).rename("is_high_dti")


@register("origination", "is_arm", dtype="bool", description="1 for ARM loans, 0 for FRM")
def _is_arm(df: pd.DataFrame) -> pd.Series:
    col = df["amortization_type"].astype(str).str.upper().str.strip()
    return (col == "ARM").astype(float).rename("is_arm")


@register(
    "origination",
    "is_jumbo",
    dtype="bool",
    description="1 when original UPB > conforming loan limit ($766,550 for 2024)",
)
def _is_jumbo(df: pd.DataFrame) -> pd.Series:
    upb = pd.to_numeric(df["orig_upb"], errors="coerce")
    return (upb > 766_550).astype(float).rename("is_jumbo")


@register(
    "origination",
    "occupancy_code",
    dtype="int8",
    description="Ordinal: P=0 (primary), I=1 (investment), S=2 (second home)",
)
def _occupancy_code(df: pd.DataFrame) -> pd.Series:
    col = df["occupancy_status"].astype(str).str.upper().str.strip()
    return col.map({"P": 0, "I": 1, "S": 2}).astype("Int8").rename("occupancy_code")


@register(
    "origination",
    "loan_purpose_code",
    dtype="int8",
    description="Ordinal: P=0 (purchase), C=1 (cashout refi), N=2 (no-cashout), R=3 (refi)",
)
def _loan_purpose_code(df: pd.DataFrame) -> pd.Series:
    col = df["loan_purpose"].astype(str).str.upper().str.strip()
    return col.map({"P": 0, "C": 1, "N": 2, "R": 3}).astype("Int8").rename("loan_purpose_code")


@register(
    "origination",
    "channel_code",
    dtype="int8",
    description="Origination channel: R=0 (retail), B=1 (broker), C=2 (correspondent), T=3 (TPO)",
)
def _channel_code(df: pd.DataFrame) -> pd.Series:
    col = df["channel"].astype(str).str.upper().str.strip()
    return col.map({"R": 0, "B": 1, "C": 2, "T": 3}).astype("Int8").rename("channel_code")


@register(
    "origination",
    "property_type_code",
    dtype="int8",
    description="Ordinal: SF=0, CO=1, PU=2, MH=3, CP=4",
)
def _property_type_code(df: pd.DataFrame) -> pd.Series:
    col = df["property_type"].astype(str).str.upper().str.strip()
    return (
        col.map({"SF": 0, "CO": 1, "PU": 2, "MH": 3, "CP": 4})
        .astype("Int8")
        .rename("property_type_code")
    )


# ---------------------------------------------------------------------------
# ── Performance features ─────────────────────────────────────────────────────
# ---------------------------------------------------------------------------


@register(
    "performance",
    "is_delinquent",
    dtype="bool",
    description="1 when delinquency status > 0 (any past-due)",
)
def _is_delinquent(df: pd.DataFrame) -> pd.Series:
    status = df["current_delinquency_status"].astype(str).str.strip()
    numeric = pd.to_numeric(status, errors="coerce")
    return (numeric > 0).astype(float).rename("is_delinquent")


@register(
    "performance",
    "delinquency_bucket",
    dtype="int8",
    description="0=current, 1=30DPD, 2=60DPD, 3=90+DPD/FC",
)
def _delinquency_bucket(df: pd.DataFrame) -> pd.Series:
    status = pd.to_numeric(df["current_delinquency_status"], errors="coerce")
    buckets = pd.cut(
        status,
        bins=[-1, 0, 1, 2, float("inf")],
        labels=[0, 1, 2, 3],
    ).astype("Int8")
    return buckets.rename("delinquency_bucket")


@register(
    "performance",
    "paydown_ratio",
    description="(orig_upb - current_actual_upb) / orig_upb — proportion paid down",
)
def _paydown_ratio(df: pd.DataFrame) -> pd.Series:
    orig_raw = df.get("orig_upb", pd.Series(pd.NA, index=df.index))
    current_raw = df.get("current_actual_upb", pd.Series(pd.NA, index=df.index))
    orig = pd.to_numeric(orig_raw, errors="coerce")
    current = pd.to_numeric(current_raw, errors="coerce")
    denom = orig.clip(lower=1)
    ratio = ((orig - current) / denom).clip(0, 1)
    return ratio.rename("paydown_ratio")


@register(
    "performance",
    "rate_spread",
    description="current_interest_rate - orig_interest_rate (positive = rate rose)",
)
def _rate_spread(df: pd.DataFrame) -> pd.Series:
    cur_raw = df.get("current_interest_rate", pd.Series(pd.NA, index=df.index))
    orig_raw = df.get("orig_interest_rate", pd.Series(pd.NA, index=df.index))
    cur_rate = pd.to_numeric(cur_raw, errors="coerce")
    orig_rate = pd.to_numeric(orig_raw, errors="coerce")
    return (cur_rate - orig_rate).rename("rate_spread")


@register(
    "performance",
    "term_remaining_ratio",
    description="remaining_months / orig_loan_term — how far through the loan",
)
def _term_remaining_ratio(df: pd.DataFrame) -> pd.Series:
    remaining_raw = df.get("remaining_months_to_legal_maturity", pd.Series(pd.NA, index=df.index))
    orig_term_raw = df.get("orig_loan_term", pd.Series(pd.NA, index=df.index))
    remaining = pd.to_numeric(remaining_raw, errors="coerce")
    orig_term = pd.to_numeric(orig_term_raw, errors="coerce")
    return (remaining / orig_term.clip(lower=1)).clip(0, 1).rename("term_remaining_ratio")


@register(
    "performance", "has_been_modified", dtype="bool", description="1 if modification_flag is Y"
)
def _has_been_modified(df: pd.DataFrame) -> pd.Series:
    col = df.get("modification_flag", pd.Series("N", index=df.index))
    return (
        (col.astype(str).str.upper().str.strip() == "Y").astype(float).rename("has_been_modified")
    )


@register(
    "performance",
    "zero_balance_flag",
    dtype="bool",
    description="1 if loan has exited (zero balance code present)",
)
def _zero_balance_flag(df: pd.DataFrame) -> pd.Series:
    col = df.get("zero_balance_code", pd.Series(pd.NA, index=df.index))
    return col.notna().astype(float).rename("zero_balance_flag")


@register(
    "performance",
    "loan_age_sq",
    description="Squared loan age — captures non-linear default hazard",
)
def _loan_age_sq(df: pd.DataFrame) -> pd.Series:
    age = pd.to_numeric(df.get("loan_age"), errors="coerce").clip(0, 480)
    return (age**2).rename("loan_age_sq")


# ---------------------------------------------------------------------------
# ── Macro stub features ───────────────────────────────────────────────────────
# Placeholders filled with NaN until FRED integration is wired up.
# ---------------------------------------------------------------------------


def _macro_stub(col_name: str) -> FeatureFn:
    def fn(df: pd.DataFrame) -> pd.Series:
        return pd.Series(np.nan, index=df.index, name=col_name, dtype="float64")

    fn.__name__ = f"_macro_{col_name}"
    return fn


for _name, _desc in [
    ("unemployment_rate", "US unemployment rate (FRED UNRATE) — macro stub"),
    ("mortgage_rate_30yr", "30-yr fixed mortgage rate (FRED MORTGAGE30US) — macro stub"),
    ("hpi_yoy", "FHFA HPI year-over-year % change — macro stub"),
]:
    register("macro_stub", _name, description=_desc)(_macro_stub(_name))
