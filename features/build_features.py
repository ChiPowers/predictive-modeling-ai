"""Feature pipeline: build a model-ready feature matrix from raw loan data.

Typical usage
-------------
From Python::

    from features.build_features import build_features, run

    # Pure transform (no I/O) — useful in tests and notebooks
    feature_df = build_features(raw_df)

    # Full pipeline: load raw parquet → build → save processed parquet
    feature_df = run("fannie-mae")

From the CLI::

    pmai features --source fannie-mae

Pipeline execution order
------------------------
1. Sort by (loan_id, observation_date) — once, before any performance features.
2. Origination features — clean and encode static origination attributes.
3. Performance features — rolling / cumulative stats that respect observation_date.
4. Macro stub features — NaN placeholders for Task 4 macro join.
5. Schema validation — assert all required columns are present.
6. Persist to ``data/processed/features.parquet``.

Leakage guarantee
-----------------
All performance features use ``rolling()`` or ``cummax``/``cumsum`` on a
DataFrame sorted by (loan_id, observation_date).  These pandas operations are
strictly backward-looking: the value at row t uses only rows ≤ t within each
loan group.  No forward-looking window functions are used.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from config.settings import settings
from features.feature_defs import FEATURE_REGISTRY, GROUP_ORDER, FeatureSpec
from utils.logging import log

_CONFIG_PATH: Path = Path(__file__).resolve().parents[1] / "config" / "features.yaml"


# ── Config helpers ────────────────────────────────────────────────────────────


def _load_config() -> dict:
    with _CONFIG_PATH.open() as fh:
        return yaml.safe_load(fh)


# ── Schema validation ────────────────────────────────────────────────────────


def _validate_schema(df: pd.DataFrame, required_cols: list[str]) -> None:
    """Raise ValueError if any required column is absent from *df*."""
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"Feature matrix is missing required columns: {missing}. "
            "Check that the raw DataFrame contains the expected input columns."
        )


# ── Core pipeline ────────────────────────────────────────────────────────────


def build_features(
    df: pd.DataFrame,
    *,
    enabled_groups: list[str] | None = None,
) -> pd.DataFrame:
    """Transform a raw loan DataFrame into a model-ready feature matrix.

    Args:
        df: Raw DataFrame.  Must contain the columns required by the enabled
            feature functions (see ``features/feature_defs.py``).
        enabled_groups: Feature groups to run.  Defaults to the
            ``enabled_groups`` list in ``config/features.yaml``.

    Returns:
        Feature DataFrame with all registered features applied and schema
        validated.  The row order matches the input after sorting by
        (loan_id, observation_date).

    Raises:
        ValueError: If required output columns are missing after pipeline runs.
    """
    cfg = _load_config()
    groups = enabled_groups or cfg.get("enabled_groups", list(GROUP_ORDER))

    # Collect specs in canonical group order
    specs: list[FeatureSpec] = [
        spec
        for group in GROUP_ORDER
        if group in groups
        for spec in FEATURE_REGISTRY.values()
        if spec.group == group
    ]

    out = df.copy()

    # Sort once so all performance features see a consistent chronological order.
    # This is the leakage guard: rolling/cumulative ops will only look backward.
    has_perf = any(s.group == "performance" for s in specs)
    if has_perf and {"loan_id", "observation_date"}.issubset(out.columns):
        out = out.sort_values(["loan_id", "observation_date"]).reset_index(drop=True)
        log.debug("DataFrame sorted by (loan_id, observation_date) for performance features")

    for spec in specs:
        missing_req = [c for c in spec.required_input_cols if c not in out.columns]
        if missing_req:
            log.warning(
                "Skipping feature '{}': missing input column(s) {}",
                spec.name,
                missing_req,
            )
            continue

        series = spec.fn(out)
        # Use numpy values to avoid pandas index-alignment surprises when the
        # feature function returns a series with a different index.
        out[spec.output_col] = series.to_numpy()
        log.debug("Feature '{}' computed ({} non-null)", spec.name, series.notna().sum())

    required_output_cols: list[str] = cfg.get("required_output_cols", [])
    if required_output_cols:
        _validate_schema(out, required_output_cols)

    log.info(
        "build_features complete: {} rows, {} feature columns",
        len(out),
        len(out.columns),
    )
    return out


# ── I/O wrapper for CLI / pipeline use ──────────────────────────────────────


def run(source: str) -> pd.DataFrame:
    """Load raw parquet for *source*, build features, and save processed parquet.

    Args:
        source: Dataset source key (must already be ingested; a parquet file
            ``data/raw/<source>.parquet`` must exist).

    Returns:
        Feature DataFrame (also written to ``data/processed/features.parquet``).
    """
    cfg = _load_config()
    raw_path = settings.data_raw_dir / f"{source}.parquet"
    log.info("Loading raw data from '{}'", raw_path)

    if not raw_path.exists():
        raise FileNotFoundError(
            f"Raw parquet not found: {raw_path}. "
            "Run 'pmai ingest --source {source}' first."
        )

    df = pd.read_parquet(raw_path)
    log.info("Loaded {} rows, {} columns", len(df), df.shape[1])

    features_df = build_features(df)

    out_path = Path(cfg.get("output_path", "data/processed/features.parquet"))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    features_df.to_parquet(out_path, index=False)
    log.info(
        "Features saved → '{}' ({} rows, {} cols)",
        out_path,
        len(features_df),
        features_df.shape[1],
    )
    return features_df
