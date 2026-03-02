"""Feature engineering pipeline."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from utils.logging import log

_FANNIE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "data_paths.yaml"


def _fannie_processed_dir() -> Path:
    with open(_FANNIE_CONFIG_PATH) as fh:
        return Path(yaml.safe_load(fh)["fannie_mae"]["processed_dir"])


def build_features(source: str) -> pd.DataFrame:
    """Transform ingested data for ``source`` into model-ready features.

    Loads the processed parquet(s), joins FRED macro indicators aligned to
    each observation month, and writes the enriched feature set to
    ``data/processed/features/<source>_features.parquet``.

    Macro join is *best-effort*: if the FRED parquet has not been generated
    yet a warning is emitted and the join is skipped so the pipeline can
    continue without macro data.

    Args:
        source: Dataset source key matching the one used during ingestion
            (e.g. ``"fannie-mae"``).

    Returns:
        Feature DataFrame (also persisted to parquet).

    Raises:
        FileNotFoundError: If no processed data is found for ``source``.
    """
    from features.macro_join import join_macro_features

    log.info("build_features called for source={}", source)

    df, date_col = _load_source(source)

    # --- Macro join ----------------------------------------------------------
    try:
        df = join_macro_features(df, date_col=date_col)
    except FileNotFoundError as exc:
        log.warning(
            "Macro features skipped — FRED parquet not found. "
            "Run 'python -m main ingest --source fred' to enable them. ({})",
            exc,
        )

    # --- Persist -------------------------------------------------------------
    out_dir = Path("data/processed/features")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{source.replace('-', '_')}_features.parquet"
    df.to_parquet(out_path, index=False, engine="pyarrow")
    log.info(
        "Features written → {} ({:,} rows, {:,} cols)",
        out_path,
        len(df),
        df.shape[1],
    )
    return df


# ---------------------------------------------------------------------------
# Source loaders
# ---------------------------------------------------------------------------


def _load_source(source: str) -> tuple[pd.DataFrame, str]:
    """Return (DataFrame, date_column_name) for a given source key.

    Raises:
        FileNotFoundError: If no processed files exist for the source.
    """
    if source == "fannie-mae":
        return _load_fannie_origination()

    # Generic fallback: look for data/processed/<source>.parquet
    generic_path = Path("data/processed") / f"{source}.parquet"
    if not generic_path.exists():
        raise FileNotFoundError(
            f"No processed data found for source '{source}'. "
            f"Expected {generic_path} or a known source key like 'fannie-mae'."
        )
    df = pd.read_parquet(generic_path)
    date_col = df.columns[0]
    log.info("Loaded {} ({:,} rows) — using '{}' as date column", generic_path, len(df), date_col)
    return df, date_col


def _load_fannie_origination() -> tuple[pd.DataFrame, str]:
    """Load the first available Fannie Mae origination parquet."""
    orig_dir = _fannie_processed_dir() / "origination"
    paths = sorted(Path(orig_dir).glob("origination_*.parquet"))
    if not paths:
        raise FileNotFoundError(
            f"No processed origination files found in {orig_dir}. "
            "Run: python -m main ingest --source fannie-mae"
        )
    df = pd.read_parquet(paths[0])
    log.info(
        "Loaded Fannie Mae origination {} ({:,} rows, {:,} cols)",
        paths[0].name,
        len(df),
        df.shape[1],
    )
    # first_payment_date is YYYYMM in Fannie Mae origination files
    return df, "first_payment_date"
