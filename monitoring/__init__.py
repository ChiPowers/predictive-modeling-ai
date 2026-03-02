"""Monitoring package — drift detection and performance tracking.

Public surface
--------------
run_monitoring_job(feature_ref, feature_cur, score_ref, score_cur,
                   labels, scores, period_col, output_dir)
    Orchestrates feature drift, score drift, and perf drift, then writes
    a consolidated Markdown summary to output_dir/summary.md.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from utils.logging import log


def run_monitoring_job(
    feature_ref: pd.DataFrame,
    feature_cur: pd.DataFrame,
    score_ref: pd.Series,
    score_cur: pd.Series,
    labels: pd.Series | None = None,
    scores: pd.Series | None = None,
    period_col: pd.Series | None = None,
    output_dir: Path = Path("reports/monitoring"),
    features: list[str] | None = None,
    auc_alert_threshold: float = 0.65,
    window: int = 3,
) -> dict[str, Any]:
    """Run the full monitoring job and write all reports.

    Args:
        feature_ref:         Reference origination DataFrame.
        feature_cur:         Current scoring-period origination DataFrame.
        score_ref:           Reference PD scores.
        score_cur:           Current PD scores.
        labels:              Binary default labels (optional — required for AUC).
        scores:              PD scores aligned to ``labels`` (optional).
        period_col:          Period column aligned to ``labels`` (optional).
        output_dir:          Directory for all JSON and Markdown output.
        features:            Feature columns to test; defaults to KEY_NUMERIC_FEATURES.
        auc_alert_threshold: AUC below this value triggers a perf alert.
        window:              Rolling AUC window in periods.

    Returns:
        Dict with ``feature_drift``, ``score_drift``, and ``perf_drift`` sub-dicts.
    """
    from monitoring.drift import run_feature_drift
    from monitoring.perf_drift import run_perf_drift
    from monitoring.score_drift import run_score_drift

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Monitoring job started → output_dir={}", output_dir)

    feat_results = run_feature_drift(
        feature_ref, feature_cur, features=features, output_dir=output_dir
    )
    score_results = run_score_drift(score_ref, score_cur, output_dir=output_dir)

    perf_results: dict[str, Any] | None = None
    if labels is not None and scores is not None and period_col is not None:
        perf_results = run_perf_drift(
            labels,
            scores,
            period_col,
            window=window,
            auc_alert_threshold=auc_alert_threshold,
            output_dir=output_dir,
        )
    else:
        log.info("Labels not provided — skipping rolling AUC (perf_drift)")

    all_results: dict[str, Any] = {
        "feature_drift": feat_results,
        "score_drift": score_results,
        "perf_drift": perf_results,
    }

    write_summary_report(all_results, output_dir)
    log.info("Monitoring job complete")
    return all_results


def write_summary_report(results: dict[str, Any], output_dir: Path) -> Path:
    """Render a human-readable Markdown summary from monitoring results.

    Args:
        results:    Output of ``run_monitoring_job``.
        output_dir: Directory where ``summary.md`` is written.

    Returns:
        Path to the written file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "summary.md"

    feat = results.get("feature_drift") or {}
    score = results.get("score_drift") or {}
    perf = results.get("perf_drift")

    run_ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    # ── overall health badge ─────────────────────────────────────────────────
    alerts: list[str] = []
    for feature, data in feat.items():
        if data.get("alert"):
            alerts.append(f"Feature `{feature}` PSI alert")
    if score.get("alert"):
        alerts.append("Score distribution alert")
    if perf and perf.get("alert"):
        alerts.append(f"AUC below threshold ({perf.get('auc_alert_threshold')})")

    status = "ALERT" if alerts else "OK"

    lines: list[str] = [
        "# Monitoring Summary",
        "",
        f"**Run:** {run_ts}  ",
        f"**Status:** {status}  ",
        "",
    ]

    # ── alert list ───────────────────────────────────────────────────────────
    if alerts:
        lines += ["## Alerts", ""]
        for a in alerts:
            lines.append(f"- {a}")
        lines.append("")

    # ── feature drift ────────────────────────────────────────────────────────
    lines += ["## Feature Drift", ""]
    if feat:
        lines += [
            "| Feature | PSI | KS stat | KS p-val | Severity |",
            "|---------|-----|---------|----------|----------|",
        ]
        for feature, data in feat.items():
            lines.append(
                f"| {feature} "
                f"| {data['psi']:.4f} "
                f"| {data['ks_statistic']:.4f} "
                f"| {data['ks_p_value']:.4f} "
                f"| {data['severity']} |"
            )
        lines.append("")
        lines += [
            "> PSI < 0.10 = ok · 0.10–0.25 = warning · > 0.25 = alert  ",
            "> KS p-value < 0.05 = alert",
            "",
        ]
    else:
        lines += ["_No feature drift results._", ""]

    # ── score drift ──────────────────────────────────────────────────────────
    lines += ["## Score Drift (PD Distribution)", ""]
    if score:
        ref_p = score.get("reference_percentiles", {})
        cur_p = score.get("current_percentiles", {})
        lines += [
            f"- **PSI:** {score.get('psi', 'N/A')}  ",
            f"- **KS statistic:** {score.get('ks_statistic', 'N/A')}  ",
            f"- **KS p-value:** {score.get('ks_p_value', 'N/A')}  ",
            f"- **Mean shift:** {score.get('mean_shift', 'N/A'):+.4f}  ",
            f"- **Severity:** {score.get('severity', 'N/A')}  ",
            "",
            "| Percentile | Reference | Current |",
            "|------------|-----------|---------|",
        ]
        for p in ["p10", "p25", "p50", "p75", "p90"]:
            lines.append(f"| {p} | {ref_p.get(p, 'N/A')} | {cur_p.get(p, 'N/A')} |")
        lines.append("")
    else:
        lines += ["_No score drift results._", ""]

    # ── performance drift ────────────────────────────────────────────────────
    lines += ["## Performance Drift (Rolling AUC)", ""]
    if perf:
        lines += [
            f"- **Latest AUC:** {perf.get('latest_auc', 'N/A')}  ",
            f"- **Trend:** {perf.get('trend', 'N/A')}  ",
            f"- **Slope:** {perf.get('slope', 'N/A')}  ",
            f"- **Alert threshold:** {perf.get('auc_alert_threshold', 'N/A')}  ",
            f"- **Alert:** {perf.get('alert', False)}  ",
            "",
            "| Period | AUC | N obs | N defaults |",
            "|--------|-----|-------|------------|",
        ]
        for row in perf.get("rolling_auc", []):
            auc_str = f"{row['auc']:.4f}" if row["auc"] is not None else "N/A"
            lines.append(
                f"| {row['period']} | {auc_str} | {row['n_obs']} | {row['n_defaults']} |"
            )
        lines.append("")
    else:
        lines += ["_Labels not yet available — rolling AUC not computed._", ""]

    lines += [
        "---",
        "_Generated by predictive-modeling-ai monitoring job._",
    ]

    out_path.write_text("\n".join(lines))
    log.info("Summary report written → {}", out_path)
    return out_path
