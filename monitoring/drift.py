"""Feature distribution drift — Population Stability Index and KS test.

Typical usage
-------------
from monitoring.drift import run_feature_drift

results = run_feature_drift(
    reference_df=train_origination,
    current_df=scoring_origination,
    output_dir=Path("reports/monitoring"),
)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from utils.logging import log

# Origination features most sensitive to population shift
KEY_NUMERIC_FEATURES: list[str] = [
    "credit_score",
    "orig_ltv",
    "orig_dti",
    "orig_upb",
    "orig_interest_rate",
    "orig_cltv",
]

# PSI thresholds (industry standard)
PSI_WARN = 0.10
PSI_ALERT = 0.25

# KS test significance level
KS_ALPHA = 0.05


def _equal_freq_edges(reference: np.ndarray[Any, np.dtype[Any]], n_bins: int) -> np.ndarray[Any, np.dtype[Any]]:
    """Return bin edges derived from reference-distribution quantiles."""
    percentiles = np.linspace(0, 100, n_bins + 1)
    edges = np.nanpercentile(reference, percentiles)
    return np.unique(edges)  # type: ignore[no-any-return]  # collapse duplicate edges for near-constant cols


def psi(reference: pd.Series, current: pd.Series, n_bins: int = 10) -> float:
    """Compute Population Stability Index (PSI) between two distributions.

    PSI < 0.10  → no significant change
    PSI 0.10–0.25 → moderate change (warning)
    PSI > 0.25  → significant change (alert)

    Args:
        reference: Baseline / training-period values.
        current:   Scoring-period values.
        n_bins:    Number of equal-frequency bins based on the reference.

    Returns:
        PSI as a non-negative float.
    """
    ref = reference.dropna().to_numpy(dtype=float)
    cur = current.dropna().to_numpy(dtype=float)

    if len(ref) == 0 or len(cur) == 0:
        log.warning("PSI skipped — empty series after dropna")
        return 0.0

    edges = _equal_freq_edges(ref, n_bins)
    if len(edges) < 2:
        return 0.0  # constant column — no drift by definition

    ref_counts, _ = np.histogram(ref, bins=edges)
    cur_counts, _ = np.histogram(cur, bins=edges)

    eps = 1e-8
    ref_pct = np.clip(ref_counts / ref_counts.sum(), eps, None)
    cur_pct = np.clip(cur_counts / cur_counts.sum(), eps, None)

    return float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))


def ks_test(reference: pd.Series, current: pd.Series) -> dict[str, float]:
    """Two-sample Kolmogorov-Smirnov test.

    Args:
        reference: Baseline values.
        current:   Scoring-period values.

    Returns:
        Dict with ``statistic`` and ``p_value`` keys.
    """
    ref = reference.dropna().to_numpy(dtype=float)
    cur = current.dropna().to_numpy(dtype=float)
    result = stats.ks_2samp(ref, cur)
    return {"statistic": float(result.statistic), "p_value": float(result.pvalue)}


def run_feature_drift(
    reference_df: pd.DataFrame,
    current_df: pd.DataFrame,
    features: list[str] | None = None,
    n_bins: int = 10,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Run PSI and KS drift checks for each numeric feature.

    Args:
        reference_df: Baseline / training-period data.
        current_df:   Scoring-period data.
        features:     Columns to test; defaults to KEY_NUMERIC_FEATURES.
        n_bins:       Number of PSI bins.
        output_dir:   If given, writes ``drift_features.json`` there.

    Returns:
        ``{feature: {psi, ks_statistic, ks_p_value, severity, alert}}``
    """
    features = features or KEY_NUMERIC_FEATURES
    results: dict[str, Any] = {}

    for feat in features:
        if feat not in reference_df.columns or feat not in current_df.columns:
            log.warning("Feature '{}' missing from one dataset — skipping", feat)
            continue

        psi_val = psi(reference_df[feat], current_df[feat], n_bins=n_bins)
        ks = ks_test(reference_df[feat], current_df[feat])

        if psi_val >= PSI_ALERT or ks["p_value"] < KS_ALPHA:
            severity = "alert"
        elif psi_val >= PSI_WARN:
            severity = "warning"
        else:
            severity = "ok"

        alert = severity == "alert"
        results[feat] = {
            "psi": round(psi_val, 6),
            "ks_statistic": round(ks["statistic"], 6),
            "ks_p_value": round(ks["p_value"], 6),
            "severity": severity,
            "alert": alert,
        }

        log_fn = log.warning if alert else log.info
        log_fn(
            "Feature drift [{}]: PSI={:.4f} KS={:.4f} p={:.4f} severity={}",
            feat,
            psi_val,
            ks["statistic"],
            ks["p_value"],
            severity,
        )

    if output_dir is not None:
        _write_json(results, Path(output_dir) / "drift_features.json")

    return results


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _write_json(data: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    log.info("Report written → {}", path)
