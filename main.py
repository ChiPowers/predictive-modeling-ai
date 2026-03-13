"""Entry-point CLI for predictive-modeling-ai.

Usage:
    python -m main ingest   --source <name>
    python -m main features --source <name>
    python -m main train    --model  <name> [--run-name <name>] [--experiment-name <name>]
    python -m main serve
    python -m main pipeline --source <name> --model <name> [--run-name <name>] [--experiment-name <name>]

Or via the installed script:
    pmai ingest --source <name>
"""
from __future__ import annotations

import typer

from config.settings import settings
from utils.logging import configure_logging, log

app = typer.Typer(
    name="pmai",
    help="Predictive Modeling AI — ingest, engineer, train, serve.",
    add_completion=False,
)


def _setup(ctx: typer.Context) -> None:  # noqa: ARG001
    configure_logging(
        level=settings.log_level,
        log_file=settings.logs_dir / "app.log",
        serialize=settings.log_serialize,
    )


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Root callback — configure logging before any sub-command runs."""
    _setup(ctx)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


# ── Sub-commands ────────────────────────────────────────────────────────────


@app.command()
def ingest(
    source: str = typer.Option(..., help="Dataset source key (e.g. 'fred', 'csv:path/to/file.csv')"),
) -> None:
    """Download and persist a raw dataset."""
    from data_ingestion.loader import load

    log.info("Starting ingestion for source={}", source)
    load(source)
    log.info("Ingestion complete")


@app.command()
def features(
    source: str = typer.Option(..., help="Dataset source key used during ingest"),
) -> None:
    """Run feature-engineering on an ingested dataset."""
    from features.engineer import build_features

    log.info("Building features for source={}", source)
    build_features(source)
    log.info("Feature engineering complete")


@app.command()
def train(
    model: str = typer.Option("prophet", help="Model identifier (prophet | sklearn-logreg | sklearn-rf)"),
    run_name: str | None = typer.Option(None, "--run-name", help="MLflow run label"),
    experiment_name: str | None = typer.Option(
        None, "--experiment-name", help="MLflow experiment name (overrides settings)"
    ),
) -> None:
    """Train a forecasting model and log the run to MLflow."""
    from training.trainer import train_model

    log.info("Training model={}", model)
    train_model(model, run_name=run_name, experiment_name=experiment_name)
    log.info("Training complete")


@app.command()
def serve() -> None:
    """Start the prediction API server."""
    import uvicorn

    log.info("Starting API on {}:{}", settings.api_host, settings.api_port)
    uvicorn.run(
        "service.api:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
    )


@app.command()
def pipeline(
    source: str = typer.Option(..., help="Dataset source key"),
    model: str = typer.Option("prophet", help="Model identifier"),
    run_name: str | None = typer.Option(None, "--run-name", help="MLflow run label"),
    experiment_name: str | None = typer.Option(
        None, "--experiment-name", help="MLflow experiment name (overrides settings)"
    ),
) -> None:
    """Run the full ingest → features → train pipeline."""
    from data_ingestion.loader import load
    from features.engineer import build_features
    from training.trainer import train_model

    log.info("Running full pipeline: source={} model={}", source, model)
    load(source)
    build_features(source)
    train_model(model, run_name=run_name, experiment_name=experiment_name)
    log.info("Pipeline complete")


@app.command()
def monitor(
    reference_path: str = typer.Option(
        ..., "--reference", "-r", help="Path to reference (baseline) parquet file"
    ),
    current_path: str = typer.Option(
        ..., "--current", "-c", help="Path to current scoring-period parquet file"
    ),
    score_ref_col: str = typer.Option(
        "pd_score", help="Column name for PD scores in the reference file"
    ),
    score_cur_col: str = typer.Option(
        "pd_score", help="Column name for PD scores in the current file"
    ),
    label_col: str = typer.Option(
        "default_flag", help="Binary label column (1=default) for rolling AUC"
    ),
    period_col: str = typer.Option(
        "monthly_reporting_period", help="Period column for rolling AUC"
    ),
    output_dir: str = typer.Option(
        "reports/monitoring", help="Directory for JSON and Markdown reports"
    ),
    window: int = typer.Option(3, help="Rolling AUC window (number of periods)"),
    auc_threshold: float = typer.Option(0.65, help="AUC alert threshold"),
) -> None:
    """Run the monitoring job: feature drift, score drift, and rolling AUC.

    Designed to be invoked on a schedule (cron, Airflow, etc.).  Reads
    reference and current datasets from parquet files, then writes:

    \b
        reports/monitoring/drift_features.json
        reports/monitoring/score_drift.json
        reports/monitoring/perf_drift.json   (only when label_col present)
        reports/monitoring/summary.md
    """
    from pathlib import Path

    import pandas as pd

    from monitoring import run_monitoring_job

    log.info("Loading reference dataset from {}", reference_path)
    ref_df = pd.read_parquet(reference_path)
    log.info("Loading current dataset from {}", current_path)
    cur_df = pd.read_parquet(current_path)

    score_ref = ref_df[score_ref_col] if score_ref_col in ref_df.columns else pd.Series(dtype=float)
    score_cur = cur_df[score_cur_col] if score_cur_col in cur_df.columns else pd.Series(dtype=float)

    # Rolling AUC is optional — only run when both label and period cols exist
    labels = cur_df[label_col] if label_col in cur_df.columns else None
    period = cur_df[period_col] if period_col in cur_df.columns else None
    auc_scores = score_cur if labels is not None else None

    run_monitoring_job(
        feature_ref=ref_df,
        feature_cur=cur_df,
        score_ref=score_ref,
        score_cur=score_cur,
        labels=labels,
        scores=auc_scores,
        period_col=period,
        output_dir=Path(output_dir),
        window=window,
        auc_alert_threshold=auc_threshold,
    )
    log.info("Monitoring complete — reports in {}", output_dir)


if __name__ == "__main__":
    app()
