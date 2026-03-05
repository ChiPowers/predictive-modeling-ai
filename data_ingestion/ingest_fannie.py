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
from pathlib import Path
from typing import Iterator

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


def _load_config() -> dict:
    with open(_CONFIG_PATH) as fh:
        return yaml.safe_load(fh)["fannie_mae"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_QUARTER_RE = re.compile(r"(\d{4}Q[1-4])", re.IGNORECASE)


def _quarter_from_path(path: Path) -> str:
    """Extract quarter string (e.g. '2023Q1') from a filename."""
    m = _QUARTER_RE.search(path.stem)
    return m.group(1) if m else path.stem


def _filter_quarters(paths: list[Path], quarters: list[str]) -> list[Path]:
    if not quarters:
        return paths
    wanted = {q.upper() for q in quarters}
    return [p for p in paths if _quarter_from_path(p).upper() in wanted]


def _read_raw_chunk(
    path: Path,
    columns: list[str],
    cfg: dict,
    chunksize: int | None = None,
) -> pd.DataFrame | Iterator[pd.DataFrame]:
    """Read a pipe-delimited Fannie Mae file with no header."""
    kwargs: dict = dict(
        sep=cfg["delimiter"],
        header=None,
        names=columns,
        dtype=str,          # read everything as str first; schema will coerce
        encoding=cfg["encoding"],
        low_memory=False,
    )
    if chunksize:
        kwargs["chunksize"] = chunksize
    return pd.read_csv(path, **kwargs)  # type: ignore[return-value]


def _normalize_blanks(df: pd.DataFrame) -> pd.DataFrame:
    """Replace empty strings and whitespace-only cells with NaN."""
    return df.replace(r"^\s*$", pd.NA, regex=True)


def _validate(df: pd.DataFrame, schema, file_label: str) -> pd.DataFrame:
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
        # Return coerced frame even when checks partially fail so pipeline
        # can continue; callers may tighten this to re-raise if needed.
        return schema.validate(df, lazy=False)


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

        for i, chunk in enumerate(reader):  # type: ignore[union-attr]
            assert isinstance(chunk, pd.DataFrame)
            chunk = _normalize_blanks(chunk)
            if validate:
                chunk = _validate(chunk, PERFORMANCE_SCHEMA, f"{src.name}[chunk {i}]")
            chunks.append(chunk)
            if (i + 1) % 10 == 0:
                log.debug("  … processed {:,} chunks ({:,} rows so far)", i + 1, (i + 1) * chunk_size)

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
    log.info(
        "Ingestion complete — {} origination, {} performance files written",
        len(orig_paths),
        len(perf_paths),
    )
    return {"origination": orig_paths, "performance": perf_paths}
