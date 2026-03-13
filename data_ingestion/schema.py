"""Pandera schemas for Fannie Mae origination and performance data.

Reference: Fannie Mae Single-Family Loan Performance Data — Data Dictionary
https://capitalmarkets.fanniemae.com/media/document/xlsx/
        FNMA_SF_Loan_Performance_Glossary.xlsx

Both files are pipe-delimited with NO header row.  Column order below
matches the official layout (32 columns each as of the 2022+ release).
"""

from __future__ import annotations

import pandera as pa
from pandera import Column, DataFrameSchema

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Nullable float column with no additional checks
_F = pa.Float64  # shorthand
_I = pa.Int64
_S = pa.String


def _nullable_float(coerce: bool = True) -> Column:
    return Column(_F, nullable=True, coerce=coerce)


def _nullable_int(coerce: bool = True) -> Column:
    return Column(_I, nullable=True, coerce=coerce)


def _categorical(values: list[str], nullable: bool = True) -> Column:
    """String column restricted to a known set of values (+ null if nullable)."""
    check = pa.Check.isin(values)
    return Column(_S, checks=check, nullable=nullable, coerce=True)


# ---------------------------------------------------------------------------
# Column name lists (order = file layout)
# ---------------------------------------------------------------------------

ORIGINATION_COLUMNS: list[str] = [
    "credit_score",
    "first_payment_date",
    "first_time_homebuyer_flag",
    "maturity_date",
    "msa",
    "mi_pct",
    "num_units",
    "occupancy_status",
    "orig_cltv",
    "orig_dti",
    "orig_upb",
    "orig_ltv",
    "orig_interest_rate",
    "channel",
    "ppm_flag",
    "amortization_type",
    "property_state",
    "property_type",
    "postal_code",
    "loan_sequence_number",
    "loan_purpose",
    "orig_loan_term",
    "num_borrowers",
    "seller_name",
    "servicer_name",
    "super_conforming_flag",
    "pre_harp_loan_seq_num",
    "program_indicator",
    "harp_indicator",
    "property_valuation_method",
    "io_indicator",
    "mi_cancellation_indicator",
]

PERFORMANCE_COLUMNS: list[str] = [
    "loan_sequence_number",
    "monthly_reporting_period",
    "current_actual_upb",
    "current_delinquency_status",
    "loan_age",
    "remaining_months_to_legal_maturity",
    "repurchase_flag",
    "modification_flag",
    "zero_balance_code",
    "zero_balance_effective_date",
    "current_interest_rate",
    "current_deferred_upb",
    "due_date_of_last_paid_installment",
    "mi_recoveries",
    "net_sales_proceeds",
    "non_mi_recoveries",
    "expenses",
    "legal_costs",
    "maintenance_and_preservation_costs",
    "taxes_and_insurance",
    "miscellaneous_expenses",
    "actual_loss_calculation",
    "modification_cost",
    "step_modification_flag",
    "deferred_payment_plan",
    "estimated_ltv",
    "zero_balance_removal_upb",
    "delinquent_accrued_interest",
    "delinquency_due_to_disaster",
    "borrower_assistance_status_code",
    "current_month_modification_cost",
    "interest_bearing_upb",
]


# ---------------------------------------------------------------------------
# Origination schema
# ---------------------------------------------------------------------------

ORIGINATION_SCHEMA = DataFrameSchema(
    columns={
        "credit_score": Column(
            _F,
            checks=[pa.Check.in_range(300, 850)],
            nullable=True,
            coerce=True,
        ),
        "first_payment_date": Column(_S, nullable=False),
        "first_time_homebuyer_flag": _categorical(["Y", "N", "9"]),
        "maturity_date": Column(_S, nullable=False),
        "msa": _nullable_int(),
        "mi_pct": Column(_F, checks=pa.Check.in_range(0, 55), nullable=True, coerce=True),
        "num_units": Column(_I, checks=pa.Check.in_range(1, 4), nullable=False, coerce=True),
        "occupancy_status": _categorical(["P", "I", "S", "9"]),
        "orig_cltv": Column(_F, checks=pa.Check.in_range(0, 200), nullable=True, coerce=True),
        "orig_dti": Column(_F, checks=pa.Check.in_range(0, 65), nullable=True, coerce=True),
        "orig_upb": Column(_F, checks=pa.Check.greater_than(0), nullable=False, coerce=True),
        "orig_ltv": Column(_F, checks=pa.Check.in_range(0, 200), nullable=True, coerce=True),
        "orig_interest_rate": Column(
            _F, checks=pa.Check.in_range(0, 20), nullable=False, coerce=True
        ),
        "channel": _categorical(["R", "B", "C", "T", "9"]),
        "ppm_flag": _categorical(["Y", "N"]),
        "amortization_type": _categorical(["FRM", "ARM"]),
        "property_state": Column(_S, nullable=True, coerce=True),
        "property_type": _categorical(["SF", "PU", "CO", "MH", "CP"]),
        "postal_code": Column(_S, nullable=True, coerce=True),
        "loan_sequence_number": Column(_S, nullable=False, unique=False),
        "loan_purpose": _categorical(["P", "C", "N", "R", "9"]),
        "orig_loan_term": Column(_I, checks=pa.Check.in_range(1, 480), nullable=False, coerce=True),
        "num_borrowers": _nullable_int(),
        "seller_name": Column(_S, nullable=True, coerce=True),
        "servicer_name": Column(_S, nullable=True, coerce=True),
        "super_conforming_flag": _categorical(["Y", "N", " ", ""]),
        "pre_harp_loan_seq_num": Column(_S, nullable=True, coerce=True),
        "program_indicator": Column(_S, nullable=True, coerce=True),
        "harp_indicator": _categorical(["Y", "N", " ", ""]),
        "property_valuation_method": Column(_S, nullable=True, coerce=True),
        "io_indicator": _categorical(["Y", "N"]),
        "mi_cancellation_indicator": Column(_S, nullable=True, coerce=True),
    },
    strict=False,  # allow additional columns if Fannie Mae adds new ones
    coerce=True,
)


# ---------------------------------------------------------------------------
# Performance schema
# ---------------------------------------------------------------------------

PERFORMANCE_SCHEMA = DataFrameSchema(
    columns={
        "loan_sequence_number": Column(_S, nullable=False),
        "monthly_reporting_period": Column(_S, nullable=False),
        "current_actual_upb": _nullable_float(),
        "current_delinquency_status": Column(_S, nullable=True, coerce=True),
        "loan_age": _nullable_int(),
        "remaining_months_to_legal_maturity": _nullable_int(),
        "repurchase_flag": Column(_S, nullable=True, coerce=True),
        "modification_flag": _categorical(["Y", "N", " ", ""]),
        "zero_balance_code": Column(_S, nullable=True, coerce=True),
        "zero_balance_effective_date": Column(_S, nullable=True, coerce=True),
        "current_interest_rate": _nullable_float(),
        "current_deferred_upb": _nullable_float(),
        "due_date_of_last_paid_installment": Column(_S, nullable=True, coerce=True),
        "mi_recoveries": _nullable_float(),
        "net_sales_proceeds": Column(_S, nullable=True, coerce=True),  # can be "U"
        "non_mi_recoveries": _nullable_float(),
        "expenses": _nullable_float(),
        "legal_costs": _nullable_float(),
        "maintenance_and_preservation_costs": _nullable_float(),
        "taxes_and_insurance": _nullable_float(),
        "miscellaneous_expenses": _nullable_float(),
        "actual_loss_calculation": _nullable_float(),
        "modification_cost": _nullable_float(),
        "step_modification_flag": _categorical(["Y", "N", " ", ""]),
        "deferred_payment_plan": _categorical(["Y", "N", " ", ""]),
        "estimated_ltv": _nullable_float(),
        "zero_balance_removal_upb": _nullable_float(),
        "delinquent_accrued_interest": _nullable_float(),
        "delinquency_due_to_disaster": _categorical(["Y", "N", " ", ""]),
        "borrower_assistance_status_code": Column(_S, nullable=True, coerce=True),
        "current_month_modification_cost": _nullable_float(),
        "interest_bearing_upb": _nullable_float(),
    },
    strict=False,
    coerce=True,
)
