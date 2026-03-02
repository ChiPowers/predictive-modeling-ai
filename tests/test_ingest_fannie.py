"""Tests for data_ingestion.ingest_fannie and data_ingestion.schema."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from data_ingestion.schema import (
    ORIGINATION_COLUMNS,
    ORIGINATION_SCHEMA,
    PERFORMANCE_COLUMNS,
    PERFORMANCE_SCHEMA,
)


# ---------------------------------------------------------------------------
# Schema column list tests
# ---------------------------------------------------------------------------


def test_origination_column_count() -> None:
    assert len(ORIGINATION_COLUMNS) == 32


def test_performance_column_count() -> None:
    assert len(PERFORMANCE_COLUMNS) == 32


def test_origination_has_required_keys() -> None:
    required = {"loan_sequence_number", "orig_upb", "orig_interest_rate", "credit_score"}
    assert required.issubset(set(ORIGINATION_COLUMNS))


def test_performance_has_required_keys() -> None:
    required = {"loan_sequence_number", "monthly_reporting_period", "current_actual_upb"}
    assert required.issubset(set(PERFORMANCE_COLUMNS))


# ---------------------------------------------------------------------------
# Schema validation tests (using synthetic DataFrames)
# ---------------------------------------------------------------------------


def _make_origination_row(**overrides) -> dict:
    """Return a dict representing one valid origination row."""
    base = {
        "credit_score": "720",
        "first_payment_date": "012023",
        "first_time_homebuyer_flag": "N",
        "maturity_date": "012053",
        "msa": "35620",
        "mi_pct": "",
        "num_units": "1",
        "occupancy_status": "P",
        "orig_cltv": "80",
        "orig_dti": "36",
        "orig_upb": "350000",
        "orig_ltv": "80",
        "orig_interest_rate": "6.5",
        "channel": "R",
        "ppm_flag": "N",
        "amortization_type": "FRM",
        "property_state": "CA",
        "property_type": "SF",
        "postal_code": "90210",
        "loan_sequence_number": "F23Q10000001",
        "loan_purpose": "P",
        "orig_loan_term": "360",
        "num_borrowers": "2",
        "seller_name": "WELLS FARGO BANK",
        "servicer_name": "WELLS FARGO BANK",
        "super_conforming_flag": "N",
        "pre_harp_loan_seq_num": "",
        "program_indicator": "",
        "harp_indicator": "N",
        "property_valuation_method": "A",
        "io_indicator": "N",
        "mi_cancellation_indicator": "",
    }
    base.update(overrides)
    return base


def _make_performance_row(**overrides) -> dict:
    base = {
        "loan_sequence_number": "F23Q10000001",
        "monthly_reporting_period": "022023",
        "current_actual_upb": "349500.00",
        "current_delinquency_status": "0",
        "loan_age": "1",
        "remaining_months_to_legal_maturity": "359",
        "repurchase_flag": "",
        "modification_flag": "N",
        "zero_balance_code": "",
        "zero_balance_effective_date": "",
        "current_interest_rate": "6.5",
        "current_deferred_upb": "",
        "due_date_of_last_paid_installment": "012023",
        "mi_recoveries": "",
        "net_sales_proceeds": "",
        "non_mi_recoveries": "",
        "expenses": "",
        "legal_costs": "",
        "maintenance_and_preservation_costs": "",
        "taxes_and_insurance": "",
        "miscellaneous_expenses": "",
        "actual_loss_calculation": "",
        "modification_cost": "",
        "step_modification_flag": "N",
        "deferred_payment_plan": "N",
        "estimated_ltv": "80",
        "zero_balance_removal_upb": "",
        "delinquent_accrued_interest": "",
        "delinquency_due_to_disaster": "N",
        "borrower_assistance_status_code": "",
        "current_month_modification_cost": "",
        "interest_bearing_upb": "349500.00",
    }
    base.update(overrides)
    return base


def test_origination_schema_validates_valid_row() -> None:
    df = pd.DataFrame([_make_origination_row()])
    validated = ORIGINATION_SCHEMA.validate(df.replace("", float("nan")), lazy=True)
    assert validated is not None
    assert len(validated) == 1


def test_performance_schema_validates_valid_row() -> None:
    df = pd.DataFrame([_make_performance_row()])
    validated = PERFORMANCE_SCHEMA.validate(df.replace("", float("nan")), lazy=True)
    assert validated is not None
    assert len(validated) == 1


def test_origination_schema_rejects_bad_credit_score() -> None:
    import pandera.errors as pe

    df = pd.DataFrame([_make_origination_row(credit_score="100")])  # below 300
    df = df.replace("", float("nan"))
    with pytest.raises((pe.SchemaError, pe.SchemaErrors)):
        ORIGINATION_SCHEMA.validate(df, lazy=False)


def test_origination_schema_allows_null_credit_score() -> None:
    """Nullable credit score (e.g. 9999 missing marker → NaN) must pass."""
    df = pd.DataFrame([_make_origination_row(credit_score="")])
    df = df.replace("", float("nan"))
    validated = ORIGINATION_SCHEMA.validate(df, lazy=True)
    assert pd.isna(validated["credit_score"].iloc[0])


# ---------------------------------------------------------------------------
# ingest_fannie helpers
# ---------------------------------------------------------------------------


def test_quarter_from_path() -> None:
    from data_ingestion.ingest_fannie import _quarter_from_path

    assert _quarter_from_path(Path("Acquisition_2023Q1.txt")) == "2023Q1"
    assert _quarter_from_path(Path("Performance_2020Q4.txt")) == "2020Q4"


def test_filter_quarters_empty_means_all() -> None:
    from data_ingestion.ingest_fannie import _filter_quarters

    paths = [Path("Acquisition_2023Q1.txt"), Path("Acquisition_2022Q4.txt")]
    assert _filter_quarters(paths, []) == paths


def test_filter_quarters_restricts() -> None:
    from data_ingestion.ingest_fannie import _filter_quarters

    paths = [Path("Acquisition_2023Q1.txt"), Path("Acquisition_2022Q4.txt")]
    result = _filter_quarters(paths, ["2023Q1"])
    assert len(result) == 1
    assert result[0].stem == "Acquisition_2023Q1"


def test_normalize_blanks() -> None:
    from data_ingestion.ingest_fannie import _normalize_blanks

    df = pd.DataFrame({"a": ["1", "  ", ""], "b": ["x", "y", "z"]})
    out = _normalize_blanks(df)
    assert pd.isna(out["a"].iloc[1])
    assert pd.isna(out["a"].iloc[2])
    assert out["b"].iloc[0] == "x"


def test_ingest_origination_no_files(tmp_path, monkeypatch) -> None:
    """ingest_origination returns empty list when directory has no matching files."""
    import yaml
    from data_ingestion import ingest_fannie

    cfg = {
        "fannie_mae": {
            "origination_dir": str(tmp_path / "orig"),
            "performance_dir": str(tmp_path / "perf"),
            "processed_dir": str(tmp_path / "processed"),
            "origination_pattern": "Acquisition_*.txt",
            "performance_pattern": "Performance_*.txt",
            "delimiter": "|",
            "encoding": "latin-1",
            "chunk_size": 500_000,
            "quarters": [],
        }
    }
    (tmp_path / "orig").mkdir(parents=True)
    (tmp_path / "perf").mkdir(parents=True)

    cfg_path = tmp_path / "data_paths.yaml"
    cfg_path.write_text(yaml.dump(cfg))

    monkeypatch.setattr(ingest_fannie, "_CONFIG_PATH", cfg_path)

    result = ingest_fannie.ingest_origination()
    assert result == []


def test_ingest_origination_with_synthetic_file(tmp_path, monkeypatch) -> None:
    """End-to-end test: write a synthetic pipe-delimited file, ingest it."""
    import yaml
    from data_ingestion import ingest_fannie

    orig_dir = tmp_path / "orig"
    perf_dir = tmp_path / "perf"
    processed_dir = tmp_path / "processed"
    orig_dir.mkdir(parents=True)
    perf_dir.mkdir(parents=True)

    cfg = {
        "fannie_mae": {
            "origination_dir": str(orig_dir),
            "performance_dir": str(perf_dir),
            "processed_dir": str(processed_dir),
            "origination_pattern": "Acquisition_*.txt",
            "performance_pattern": "Performance_*.txt",
            "delimiter": "|",
            "encoding": "latin-1",
            "chunk_size": 500_000,
            "quarters": [],
        }
    }

    # Write one synthetic origination file
    row = _make_origination_row()
    row_str = "|".join(str(row[c]) for c in ORIGINATION_COLUMNS)
    acq_file = orig_dir / "Acquisition_2023Q1.txt"
    acq_file.write_text(row_str + "\n", encoding="latin-1")

    cfg_path = tmp_path / "data_paths.yaml"
    cfg_path.write_text(yaml.dump(cfg))

    monkeypatch.setattr(ingest_fannie, "_CONFIG_PATH", cfg_path)

    written = ingest_fannie.ingest_origination(validate=False)
    assert len(written) == 1
    result_df = pd.read_parquet(written[0])
    assert len(result_df) == 1
    assert "loan_sequence_number" in result_df.columns
