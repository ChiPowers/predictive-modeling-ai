"""PD score distribution drift monitoring.

Tracks how the distribution of predicted probability-of-default (PD) scores
shifts between a reference period (e.g. training window) and the current
scoring period.  Uses the same PSI and KS primitives as feature drift.

Typical usage
-------------
from monitoring.score_drift import run_score_drift

results = run_score_drift(
    reference_scores=train_pd_scores,
    current_scores=current_pd_scores,
    output_dir=Path("reports/monitoring"),
)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from monitoring.drift import KS_ALPHA, PSI_ALERT, PSI_WARN, _write_json, ks_test, psi
from utils.logging import log

# Default number of equal-frequency bins for PD score PSI
DEFAULT_N_BINS = 10

# Percentiles reported in the output
REPORT_PERCENTILES = [10, 25, 50, 75, 90]

# Guardrail against large-sample false positives: require meaningful distance
# before elevating KS p-value significance to an alert.
KS_STAT_ALERT = 0.30


def _percentile_dict(series: pd.Series) -> dict[str, float]:
    arr = series.dropna().to_numpy(dtype=float)
    values = np.nanpercentile(arr, REPORT_PERCENTILES).tolist()
    return {f"p{p}": round(v, 6) for p, v in zip(REPORT_PERCENTILES, values, strict=False)}


def run_score_drift(
    reference_scores: pd.Series,
    current_scores: pd.Series,
    n_bins: int = DEFAULT_N_BINS,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Detect drift in PD score distributions.

    Args:
        reference_scores: Baseline predicted PD scores (values in [0, 1]).
        current_scores:   Current scoring-period PD scores.
        n_bins:           Number of equal-frequency PSI bins.
        output_dir:       If given, writes ``score_drift.json`` there.

    Returns:
        Dict with keys:
        - ``psi``                  PSI between distributions.
        - ``ks_statistic``         KS test statistic.
        - ``ks_p_value``           KS two-sample p-value.
        - ``reference_percentiles`` p10/p25/p50/p75/p90 of reference.
        - ``current_percentiles``  p10/p25/p50/p75/p90 of current.
        - ``mean_shift``           current_mean − reference_mean.
        - ``severity``             "ok" | "warning" | "alert".
        - ``alert``                True when severity == "alert".
    """
    psi_val = psi(reference_scores, current_scores, n_bins=n_bins)
    ks = ks_test(reference_scores, current_scores)

    ref_mean = float(reference_scores.dropna().mean())
    cur_mean = float(current_scores.dropna().mean())
    mean_shift = round(cur_mean - ref_mean, 6)

    if psi_val >= PSI_ALERT or (ks["p_value"] < KS_ALPHA and ks["statistic"] >= KS_STAT_ALERT):
        severity = "alert"
    elif psi_val >= PSI_WARN:
        severity = "warning"
    else:
        severity = "ok"

    result: dict[str, Any] = {
        "psi": round(psi_val, 6),
        "ks_statistic": round(ks["statistic"], 6),
        "ks_p_value": round(ks["p_value"], 6),
        "reference_percentiles": _percentile_dict(reference_scores),
        "current_percentiles": _percentile_dict(current_scores),
        "mean_shift": mean_shift,
        "severity": severity,
        "alert": severity == "alert",
    }

    log_fn = log.warning if result["alert"] else log.info
    log_fn(
        "Score drift: PSI={:.4f} KS={:.4f} p={:.4f} mean_shift={:+.4f} severity={}",
        psi_val,
        ks["statistic"],
        ks["p_value"],
        mean_shift,
        severity,
    )

    if output_dir is not None:
        _write_json(result, Path(output_dir) / "score_drift.json")

    return result
