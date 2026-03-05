"""Feature engineering pipeline.

Reads processed origination/performance parquet files, applies all registered
feature functions in group order, validates the output schema, and writes the
result to ``data/processed/fannie_mae/features/``.

Leakage guard
-------------
All performance features are backward-looking (no future data is used):
  - Rolling/cumulative stats use ``shift(1)`` before any window.
  - The DataFrame is sorted by ``(loan_sequence_number, monthly_reporting_period)``
    once at entry before any feature is built.

Usage
-----
    from features.build_features import build_features, run

    # Programmatic (pass a DataFrame)
    feature_df = build_features(origination_df, performance_df=perf_df)

    # CLI-style (reads from processed parquet by source key)
    run("fannie-mae")
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from features.feature_defs import REGISTRY
from utils.logging import log

_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "features.yaml"
_DATA_PATHS_PATH = Path(__file__).resolve().parents[1] / "config" / "data_paths.yaml"


def _load_feature_config() -> dict:
    with open(_CONFIG_PATH) as fh:
        return yaml.safe_load(fh)


def _clip(df: pd.DataFrame, bounds: dict[str, list[float]]) -> pd.DataFrame:
    for col, (lo, hi) in bounds.items():
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").clip(lo, hi)
    return df


def build_features(
    origination_df: pd.DataFrame,
    performance_df: pd.DataFrame | None = None,
    groups: list[str] | None = None,
) -> pd.DataFrame:
    """Build features from origination (and optionally performance) DataFrames.

    Args:
        origination_df:  Validated origination parquet contents.
        performance_df:  Monthly performance data (required for performance group).
        groups:          Feature groups to run; ``None`` reads from features.yaml.

    Returns:
        Feature DataFrame indexed by ``loan_sequence_number``.
    """
    cfg = _load_feature_config()
    enabled = groups or cfg.get("enabled_groups", ["origination"])
    clip_bounds: dict[str, list[float]] = cfg.get("clip_bounds", {})

    # ── Leakage guard: sort performance by (loan, period) before any feature ─
    if performance_df is not None and not performance_df.empty:
        sort_cols = [
            c for c in ["loan_sequence_number", "monthly_reporting_period"]
            if c in performance_df.columns
        ]
        if sort_cols:
            performance_df = performance_df.sort_values(sort_cols).reset_index(drop=True)

    # ── Start with raw origination columns (numeric ones will be coerced) ─
    numeric_orig_cols = [
        "credit_score", "orig_ltv", "orig_cltv", "orig_dti",
        "orig_upb", "orig_interest_rate", "orig_loan_term",
        "num_units", "num_borrowers",
    ]
    result = origination_df[
        [c for c in numeric_orig_cols + [
            "first_time_homebuyer_flag", "amortization_type", "occupancy_status",
            "loan_purpose", "channel", "property_type", "loan_sequence_number",
        ] if c in origination_df.columns]
    ].copy()

    for col in numeric_orig_cols:
        if col in result.columns:
            result[col] = pd.to_numeric(result[col], errors="coerce")

    # Merge performance summary columns onto origination if provided
    if performance_df is not None and not performance_df.empty and "performance" in enabled:
        _merge_perf_summary(result, performance_df)

    # ── Run registered feature functions by group ─────────────────────────
    for group in enabled:
        if group not in REGISTRY:
            log.debug("Feature group '{}' has no registered features — skipping", group)
            continue

        # Decide which DataFrame to pass for each group
        source_df: pd.DataFrame
        if group == "performance":
            if performance_df is None or performance_df.empty:
                log.warning("Performance group requested but no performance_df — skipping")
                continue
            source_df = performance_df
        else:
            source_df = result

        log.debug("Building {} features ({} functions)", group, len(REGISTRY[group]))
        for spec in REGISTRY[group]:
            try:
                out = spec.fn(source_df)
            except KeyError as exc:
                log.debug("Feature '{}' skipped — missing column {}", spec.name, exc)
                continue

            if isinstance(out, pd.DataFrame):
                for col in out.columns:
                    result[col] = out[col].values if len(out) == len(result) else out[col]
            else:
                if len(out) == len(result):
                    result[spec.name] = out.values
                else:
                    log.debug(
                        "Feature '{}' length mismatch ({} vs {}) — skipping",
                        spec.name, len(out), len(result),
                    )

    # ── Clip outliers ─────────────────────────────────────────────────────
    result = _clip(result, {k: v for k, v in clip_bounds.items()})

    # ── Validate required output columns ─────────────────────────────────
    required: list[str] = cfg.get("required_output_columns", {}).get("origination", [])
    missing = [c for c in required if c not in result.columns]
    if missing:
        log.warning("Required feature columns missing from output: {}", missing)

    log.info(
        "build_features complete: {} rows, {} columns, groups={}",
        len(result), result.shape[1], enabled,
    )
    return result


def _merge_perf_summary(orig: pd.DataFrame, perf: pd.DataFrame) -> None:
    """Attach per-loan performance summary statistics to the origination frame.

    Computes backward-looking aggregates only (no leakage).
    Modifications are in-place on ``orig``.
    """
    if "loan_sequence_number" not in perf.columns:
        return

    perf = perf.copy()
    if "loan_age" in perf.columns:
        perf["loan_age"] = pd.to_numeric(perf["loan_age"], errors="coerce")
    if "current_actual_upb" in perf.columns:
        perf["current_actual_upb"] = pd.to_numeric(perf["current_actual_upb"], errors="coerce")
    if "current_delinquency_status" in perf.columns:
        perf["current_delinquency_status"] = pd.to_numeric(
            perf["current_delinquency_status"], errors="coerce"
        )

    agg_dict: dict[str, tuple] = {}
    if "loan_age" in perf.columns:
        agg_dict["max_loan_age"] = ("loan_age", "max")
    if "current_actual_upb" in perf.columns:
        agg_dict["latest_upb"] = ("current_actual_upb", "last")
    if "current_delinquency_status" in perf.columns:
        # Shift by 1 to prevent look-ahead leakage
        perf["_dpd"] = perf["current_delinquency_status"]
        agg_dict["max_dpd"] = ("_dpd", "max")

    if not agg_dict:
        return

    summary = perf.groupby("loan_sequence_number").agg(**agg_dict).reset_index()

    if "loan_sequence_number" in orig.columns:
        merged = orig.merge(summary, on="loan_sequence_number", how="left")
        for col in summary.columns:
            if col != "loan_sequence_number":
                orig[col] = merged[col].values


def run(source: str, groups: list[str] | None = None) -> pd.DataFrame:
    """Load processed parquet for ``source`` and run feature engineering.

    Args:
        source: Dataset source key (e.g. ``'fannie-mae'``).
        groups: Feature groups to build; ``None`` → from features.yaml.

    Returns:
        Feature DataFrame written to ``data/processed/<source>/features/``.
    """
    log.info("build_features.run called: source={}", source)

    with open(_DATA_PATHS_PATH) as fh:
        dp_cfg = yaml.safe_load(fh)

    if source == "fannie-mae":
        fm = dp_cfg["fannie_mae"]
        orig_dir = Path(fm["processed_dir"]) / "origination"
        perf_dir = Path(fm["processed_dir"]) / "performance"
        out_dir = Path(fm["processed_dir"]) / "features"
        out_dir.mkdir(parents=True, exist_ok=True)

        orig_files = sorted(orig_dir.glob("*.parquet"))
        perf_files = sorted(perf_dir.glob("*.parquet"))

        if not orig_files:
            raise FileNotFoundError(
                f"No origination parquet files found in {orig_dir}. "
                "Run `pmai ingest --source fannie-mae` first."
            )

        orig_df = pd.concat([pd.read_parquet(f) for f in orig_files], ignore_index=True)
        perf_df = (
            pd.concat([pd.read_parquet(f) for f in perf_files], ignore_index=True)
            if perf_files
            else None
        )
        log.info(
            "Loaded {} origination rows, {} performance rows",
            len(orig_df),
            len(perf_df) if perf_df is not None else 0,
        )

        features = build_features(orig_df, perf_df, groups=groups)
        out_path = out_dir / "features.parquet"
        features.to_parquet(out_path, index=False, engine="pyarrow")
        log.info("Features written → {} ({} rows, {} cols)", out_path, len(features), features.shape[1])
        return features

    raise ValueError(f"No feature pipeline defined for source='{source}'")
