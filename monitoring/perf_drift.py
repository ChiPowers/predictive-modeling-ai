"""Rolling AUC performance drift — tracks discrimination power over time.

Once actual default labels become available (typically 12–24 months after
origination), this module computes AUC over a rolling window of periods.
A declining trend or sub-threshold AUC triggers an alert.

Typical usage
-------------
from monitoring.perf_drift import run_perf_drift

results = run_perf_drift(
    labels=performance_df["default_flag"],
    scores=performance_df["pd_score"],
    period_col=performance_df["monthly_reporting_period"],
    window=3,
    output_dir=Path("reports/monitoring"),
)
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from monitoring.drift import _write_json
from utils.logging import log

# AUC below this value triggers an alert
DEFAULT_AUC_ALERT_THRESHOLD = 0.65

# Rolling window (number of periods)
DEFAULT_WINDOW = 3


def rolling_auc(
    labels: pd.Series,
    scores: pd.Series,
    period_col: pd.Series,
    window: int = DEFAULT_WINDOW,
) -> pd.DataFrame:
    """Compute AUC over a rolling window of periods.

    Each row in the output represents one period and aggregates the current
    and preceding ``window - 1`` periods so the estimate is stable even when
    individual periods have few observations.

    Args:
        labels:     Binary actual default labels (1 = default, 0 = current).
        scores:     Predicted PD scores in [0, 1].
        period_col: Period identifier (e.g. monthly_reporting_period string).
        window:     Number of consecutive periods to include per estimate.

    Returns:
        DataFrame with columns ``period``, ``auc``, ``n_obs``, ``n_defaults``.
        ``auc`` is ``None`` when fewer than two classes are present.
    """
    df = pd.DataFrame(
        {
            "label": labels.to_numpy(),
            "score": scores.to_numpy(),
            "period": period_col.to_numpy(),
        }
    )
    periods = sorted(df["period"].unique())
    records = []

    for i, period in enumerate(periods):
        start = max(0, i - window + 1)
        window_periods = periods[start : i + 1]
        subset = df[df["period"].isin(window_periods)]

        n_obs = len(subset)
        n_defaults = int(subset["label"].sum())
        n_classes = int(subset["label"].nunique())

        if n_classes < 2:
            auc: float | None = None
            log.debug("Period {}: only one class in window — AUC unavailable", period)
        else:
            try:
                auc = float(roc_auc_score(subset["label"], subset["score"]))
            except Exception as exc:
                auc = None
                log.warning("AUC failed for period {}: {}", period, exc)

        records.append(
            {
                "period": str(period),
                "auc": round(auc, 6) if auc is not None else None,
                "n_obs": n_obs,
                "n_defaults": n_defaults,
            }
        )

    return pd.DataFrame(records)


def run_perf_drift(
    labels: pd.Series,
    scores: pd.Series,
    period_col: pd.Series,
    window: int = DEFAULT_WINDOW,
    auc_alert_threshold: float = DEFAULT_AUC_ALERT_THRESHOLD,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Run rolling AUC analysis and detect performance drift.

    Args:
        labels:              Binary default labels (1 = default).
        scores:              Predicted PD scores in [0, 1].
        period_col:          Period identifier column (same index as labels).
        window:              Rolling window size in periods.
        auc_alert_threshold: Alert when latest AUC drops below this value.
        output_dir:          If given, writes ``perf_drift.json`` there.

    Returns:
        Dict with keys:
        - ``rolling_auc``          List of per-period AUC records.
        - ``latest_auc``           Most recent valid AUC (or None).
        - ``trend``                "improving" | "degrading" | "insufficient_data".
        - ``slope``                OLS slope of AUC over time (or None).
        - ``auc_alert_threshold``  Threshold used for alerting.
        - ``alert``                True when latest AUC < threshold.
    """
    rolling = rolling_auc(labels, scores, period_col, window)

    valid_aucs = rolling["auc"].dropna()
    latest_auc: float | None = float(valid_aucs.iloc[-1]) if len(valid_aucs) else None

    if len(valid_aucs) >= 2:
        slope: float | None = float(
            np.polyfit(range(len(valid_aucs)), valid_aucs.to_numpy(dtype=float), 1)[0]
        )
        trend = "improving" if slope > 0 else "degrading"
    else:
        slope = None
        trend = "insufficient_data"

    alert = latest_auc is not None and latest_auc < auc_alert_threshold

    result: dict[str, Any] = {
        "rolling_auc": rolling.to_dict(orient="records"),
        "latest_auc": round(latest_auc, 6) if latest_auc is not None else None,
        "trend": trend,
        "slope": round(slope, 6) if slope is not None else None,
        "auc_alert_threshold": auc_alert_threshold,
        "alert": alert,
    }

    log_fn = log.warning if alert else log.info
    log_fn(
        "Perf drift: latest_AUC={} trend={} alert={}",
        f"{latest_auc:.4f}" if latest_auc is not None else "N/A",
        trend,
        alert,
    )

    if output_dir is not None:
        _write_json(result, Path(output_dir) / "perf_drift.json")

    return result
