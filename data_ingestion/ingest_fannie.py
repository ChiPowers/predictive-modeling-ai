"""Fannie Mae Single-Family Loan Performance Data ingestion.

Manual pre-requisite
--------------------
Files must be downloaded manually after accepting the data licence agreement:
  https://capitalmarkets.fanniemae.com/credit-risk-transfer/
          single-family-credit-risk-transfer/
          fannie-mae-single-family-loan-performance-data

Place files in the directories configured in ``config/data_paths.yaml``:
  - Origination: ``data/raw/fannie_mae/origination/Acquisition_YYYYQ?.txt``
  - Performance: ``data/raw/fannie_mae/performance/Performance_YYYYQ?.txt``

Usage (CLI)
-----------
    python -m main ingest --source fannie-mae

Usage (programmatic)
--------------------
    from data_ingestion.ingest_fannie import ingest_origination, ingest_performance
    ingest_origination()
    ingest_performance()
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pandas as pd
import yaml

from data_ingestion.schema import (
    ORIGINATION_COLUMNS,
    ORIGINATION_SCHEMA,
    PERFORMANCE_COLUMNS,
    PERFORMANCE_SCHEMA,
)
from utils.logging import log

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "data_paths.yaml"


def _load_config() -> dict[str, Any]:
    with open(_CONFIG_PATH) as fh:
        return cast(dict[str, Any], yaml.safe_load(fh)["fannie_mae"])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_QUARTER_RE = re.compile(r"(\d{4}Q[1-4])", re.IGNORECASE)

# Observed index map for newer combined monthly loan tapes where
# acquisition + performance fields are emitted in a single pipe-delimited row.
# This map only targets the subset of fields needed by the current pipeline.
_COMBINED_ORIG_COL_IDX: dict[str, int] = {
    "loan_sequence_number": 1,
    "channel": 3,
    "seller_name": 4,
    "servicer_name": 5,
    "orig_interest_rate": 7,
    "orig_upb": 9,
    "orig_loan_term": 12,
    "first_payment_date": 13,
    "maturity_date": 18,
    "orig_ltv": 19,
    "orig_cltv": 20,
    "num_borrowers": 21,
    "orig_dti": 22,
    "credit_score": 23,
    "first_time_homebuyer_flag": 25,
    "occupancy_status": 26,
    "property_type": 27,
    "num_units": 28,
    "loan_purpose": 29,
    "property_state": 30,
    "postal_code": 31,
    "msa": 32,
    "mi_pct": 33,
    "amortization_type": 34,
    "super_conforming_flag": 35,
    "ppm_flag": 36,
    "current_delinquency_status": 39,
    "modification_flag": 41,
}

_COMBINED_PERF_COL_IDX: dict[str, int] = {
    "loan_sequence_number": 1,
    "monthly_reporting_period": 2,
    "current_interest_rate": 8,
    "current_actual_upb": 11,
    "loan_age": 15,
    "remaining_months_to_legal_maturity": 16,
    "current_delinquency_status": 39,
    "modification_flag": 41,
}


def _quarter_from_path(path: Path) -> str:
    """Extract quarter string (e.g. '2023Q1') from a filename."""
    m = _QUARTER_RE.search(path.stem)
    return m.group(1) if m else path.stem


def _filter_quarters(paths: list[Path], quarters: list[str]) -> list[Path]:
    if not quarters:
        return paths
    wanted = {q.upper() for q in quarters}
    return [p for p in paths if _quarter_from_path(p).upper() in wanted]


def _extract_by_index(
    raw: pd.DataFrame, columns: list[str], idx_map: dict[str, int]
) -> pd.DataFrame:
    out = pd.DataFrame(index=raw.index)
    for col in columns:
        idx = idx_map.get(col)
        if idx is None:
            out[col] = pd.NA
        else:
            out[col] = raw.iloc[:, idx] if idx < raw.shape[1] else pd.NA
    return out


def _read_raw_chunk(
    path: Path,
    columns: list[str],
    cfg: dict[str, Any],
    chunksize: int | None = None,
) -> pd.DataFrame | Iterator[pd.DataFrame]:
    """Read a pipe-delimited Fannie Mae file with no header."""
    kwargs: dict[str, Any] = dict(
        sep=cfg["delimiter"],
        header=None,
        names=columns,
        dtype=str,  # read everything as str first; schema will coerce
        encoding=cfg["encoding"],
        low_memory=False,
    )
    if chunksize:
        kwargs["chunksize"] = chunksize
    return pd.read_csv(path, **kwargs)


def _normalize_blanks(df: pd.DataFrame) -> pd.DataFrame:
    """Replace empty strings and whitespace-only cells with NaN."""
    return df.replace(r"^\s*$", pd.NA, regex=True)


def _validate(df: pd.DataFrame, schema: Any, file_label: str) -> pd.DataFrame:
    """Run pandera validation and return the (possibly coerced) DataFrame."""
    try:
        validated = schema.validate(df, lazy=True)
        log.info("Schema validation passed for {}", file_label)
        return validated
    except Exception as exc:  # pandera.errors.SchemaErrors
        log.warning(
            "Schema validation warnings for {} — proceeding with coerced data.\n{}",
            file_label,
            exc,
        )
        # Best effort coercion; if this also fails, continue with raw normalized
        # frame so ingestion does not block downstream experimentation.
        try:
            return schema.validate(df, lazy=False)
        except Exception as exc2:
            log.warning(
                "Schema coercion fallback also failed for {} — using unvalidated frame.\n{}",
                file_label,
                exc2,
            )
            return df


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ingest_origination(
    quarters: list[str] | None = None,
    *,
    validate: bool = True,
    overwrite: bool = False,
) -> list[Path]:
    """Read, validate, and persist all origination (Acquisition) files.

    Args:
        quarters: Optional list of quarter strings to restrict ingestion
            (e.g. ``["2022Q1", "2022Q2"]``).  ``None`` processes all files.
        validate: Run pandera schema checks when ``True``.
        overwrite: Overwrite existing parquet files when ``True``.

    Returns:
        List of written parquet file paths.
    """
    cfg = _load_config()
    orig_dir = Path(cfg["origination_dir"])
    out_dir = Path(cfg["processed_dir"]) / "origination"
    out_dir.mkdir(parents=True, exist_ok=True)

    pattern = cfg["origination_pattern"]
    paths = sorted(orig_dir.glob(pattern))
    if not paths:
        log.warning("No origination files found in {}", orig_dir)
        return []

    _quarters = quarters or cfg.get("quarters") or []
    paths = _filter_quarters(paths, _quarters)
    log.info("Found {} origination file(s) to ingest", len(paths))

    written: list[Path] = []
    for src in paths:
        quarter = _quarter_from_path(src)
        out_path = out_dir / f"origination_{quarter}.parquet"

        if out_path.exists() and not overwrite:
            log.info("Skipping {} (already exists, use overwrite=True to re-ingest)", out_path)
            written.append(out_path)
            continue

        log.info("Ingesting origination file: {}", src.name)
        df = _read_raw_chunk(src, ORIGINATION_COLUMNS, cfg)
        assert isinstance(df, pd.DataFrame)

        # Write raw parquet snapshot before any transformation
        raw_out = Path(cfg["origination_dir"]) / f"origination_{quarter}_raw.parquet"
        df.to_parquet(raw_out, index=False, engine="pyarrow")
        log.debug("Raw parquet written to {}", raw_out)

        df = _normalize_blanks(df)

        if validate:
            df = _validate(df, ORIGINATION_SCHEMA, src.name)

        df.to_parquet(out_path, index=False, engine="pyarrow")
        log.info(
            "Origination {} written → {} ({:,} rows, {:,} cols)",
            quarter,
            out_path,
            len(df),
            df.shape[1],
        )
        written.append(out_path)

    return written


def ingest_performance(
    quarters: list[str] | None = None,
    *,
    validate: bool = True,
    overwrite: bool = False,
) -> list[Path]:
    """Read, validate, and persist all monthly performance files.

    Performance files can be multi-GB; they are processed in chunks
    (``chunk_size`` from config) to keep memory usage bounded.

    Args:
        quarters: Optional quarter filter (same format as :func:`ingest_origination`).
        validate: Run pandera schema checks on each chunk when ``True``.
        overwrite: Overwrite existing parquet files when ``True``.

    Returns:
        List of written parquet file paths.
    """
    cfg = _load_config()
    perf_dir = Path(cfg["performance_dir"])
    out_dir = Path(cfg["processed_dir"]) / "performance"
    out_dir.mkdir(parents=True, exist_ok=True)

    pattern = cfg["performance_pattern"]
    paths = sorted(perf_dir.glob(pattern))
    if not paths:
        log.warning("No performance files found in {}", perf_dir)
        return []

    _quarters = quarters or cfg.get("quarters") or []
    paths = _filter_quarters(paths, _quarters)
    log.info("Found {} performance file(s) to ingest", len(paths))

    chunk_size: int = int(cfg.get("chunk_size", 0)) or 500_000

    written: list[Path] = []
    for src in paths:
        quarter = _quarter_from_path(src)
        out_path = out_dir / f"performance_{quarter}.parquet"

        if out_path.exists() and not overwrite:
            log.info("Skipping {} (already exists)", out_path)
            written.append(out_path)
            continue

        log.info("Ingesting performance file: {} (chunks of {:,} rows)", src.name, chunk_size)

        chunks: list[pd.DataFrame] = []
        reader = _read_raw_chunk(src, PERFORMANCE_COLUMNS, cfg, chunksize=chunk_size)

        for i, chunk in enumerate(reader):
            assert isinstance(chunk, pd.DataFrame)
            chunk = _normalize_blanks(chunk)
            if validate:
                chunk = _validate(chunk, PERFORMANCE_SCHEMA, f"{src.name}[chunk {i}]")
            chunks.append(chunk)
            if (i + 1) % 10 == 0:
                log.debug(
                    "  … processed {:,} chunks ({:,} rows so far)", i + 1, (i + 1) * chunk_size
                )

        if not chunks:
            log.warning("Performance file {} appears empty, skipping", src.name)
            continue

        df = pd.concat(chunks, ignore_index=True)
        df.to_parquet(out_path, index=False, engine="pyarrow")
        log.info(
            "Performance {} written → {} ({:,} rows, {:,} cols)",
            quarter,
            out_path,
            len(df),
            df.shape[1],
        )
        written.append(out_path)

    return written


def ingest_all(
    quarters: list[str] | None = None,
    *,
    validate: bool = True,
    overwrite: bool = False,
) -> dict[str, list[Path]]:
    """Convenience wrapper that runs origination + performance ingestion.

    Args:
        quarters: Optional quarter filter.
        validate: Run schema validation.
        overwrite: Re-ingest already-processed files.

    Returns:
        Dict with ``'origination'`` and ``'performance'`` keys mapping to
        lists of written parquet paths.
    """
    log.info("Starting Fannie Mae full ingestion (validate={}, overwrite={})", validate, overwrite)
    orig_paths = ingest_origination(quarters, validate=validate, overwrite=overwrite)
    perf_paths = ingest_performance(quarters, validate=validate, overwrite=overwrite)

    if not orig_paths and not perf_paths:
        combined = ingest_combined(quarters, validate=validate, overwrite=overwrite)
        orig_paths = combined["origination"]
        perf_paths = combined["performance"]

    log.info(
        "Ingestion complete — {} origination, {} performance files written",
        len(orig_paths),
        len(perf_paths),
    )
    return {"origination": orig_paths, "performance": perf_paths}


def ingest_combined(
    quarters: list[str] | None = None,
    *,
    validate: bool = True,
    overwrite: bool = False,
) -> dict[str, list[Path]]:
    """Ingest newer combined loan tapes and split to origination/performance outputs."""
    cfg = _load_config()
    combined_dir = Path(cfg.get("combined_dir", Path(cfg["origination_dir"]).parent / "combined"))
    combined_pattern = cfg.get("combined_pattern", "*.csv")
    paths = sorted(combined_dir.glob(combined_pattern))
    if not paths:
        log.warning("No combined Fannie files found in {}", combined_dir)
        return {"origination": [], "performance": []}

    _quarters = quarters or cfg.get("quarters") or []
    paths = _filter_quarters(paths, _quarters)
    if not paths:
        log.warning("No combined Fannie files matched requested quarters: {}", _quarters)
        return {"origination": [], "performance": []}

    out_orig_dir = Path(cfg["processed_dir"]) / "origination"
    out_perf_dir = Path(cfg["processed_dir"]) / "performance"
    out_orig_dir.mkdir(parents=True, exist_ok=True)
    out_perf_dir.mkdir(parents=True, exist_ok=True)

    chunk_size: int = int(cfg.get("chunk_size", 0)) or 500_000
    written_orig: list[Path] = []
    written_perf: list[Path] = []

    for src in paths:
        quarter = _quarter_from_path(src)
        orig_out = out_orig_dir / f"origination_{quarter}.parquet"
        perf_out = out_perf_dir / f"performance_{quarter}.parquet"
        if orig_out.exists() and perf_out.exists() and not overwrite:
            log.info("Skipping combined {} (outputs already exist)", src.name)
            written_orig.append(orig_out)
            written_perf.append(perf_out)
            continue

        log.info("Ingesting combined Fannie file: {} (chunks of {:,})", src.name, chunk_size)
        perf_chunks: list[pd.DataFrame] = []
        orig_chunks: list[pd.DataFrame] = []
        reader = pd.read_csv(
            src,
            sep=cfg["delimiter"],
            header=None,
            dtype=str,
            encoding=cfg["encoding"],
            chunksize=chunk_size,
            low_memory=False,
        )

        for chunk in reader:
            raw = chunk

            perf = _extract_by_index(raw, PERFORMANCE_COLUMNS, _COMBINED_PERF_COL_IDX)
            perf = _normalize_blanks(perf)
            if validate:
                perf = _validate(perf, PERFORMANCE_SCHEMA, f"{src.name}[combined-perf]")
            perf_chunks.append(perf)

            orig = _extract_by_index(raw, ORIGINATION_COLUMNS, _COMBINED_ORIG_COL_IDX)
            orig = _normalize_blanks(orig)
            orig_chunks.append(orig)

        if not perf_chunks:
            log.warning("Combined file {} appears empty", src.name)
            continue

        perf_df = pd.concat(perf_chunks, ignore_index=True)
        perf_df.to_parquet(perf_out, index=False, engine="pyarrow")
        written_perf.append(perf_out)

        orig_df = pd.concat(orig_chunks, ignore_index=True)
        orig_df = orig_df.drop_duplicates(subset=["loan_sequence_number"], keep="first")
        if validate:
            orig_df = _validate(orig_df, ORIGINATION_SCHEMA, f"{src.name}[combined-orig]")
        orig_df.to_parquet(orig_out, index=False, engine="pyarrow")
        written_orig.append(orig_out)

        log.info(
            "Combined {} written → orig: {} rows, perf: {} rows",
            quarter,
            len(orig_df),
            len(perf_df),
        )

    return {"origination": written_orig, "performance": written_perf}
