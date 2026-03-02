"""FastAPI prediction service.

Endpoints
---------
GET  /health
    Liveness probe — returns {"status": "ok"}.

POST /forecast
    Generate a time-series forecast using a saved model artifact.
    Body: ForecastRequest  →  ForecastResponse

POST /score
    Score a batch of loans with a PD (probability-of-default) model.
    Body: ScoreRequest  →  ScoreResponse
"""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from config.settings import settings
from utils.logging import configure_logging, log

# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    configure_logging(level=settings.log_level, serialize=settings.log_serialize)
    log.info("API starting up")
    yield
    log.info("API shutting down")


app = FastAPI(
    title="Predictive Modeling AI",
    description="Historic and forecasted trend visualisation and PD scoring API",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ForecastRequest(BaseModel):
    source: str = Field(..., description="Dataset source key (e.g. 'fannie-mae')")
    model: str = Field(default="prophet", description="Model key to use for forecasting")
    horizon: int = Field(
        default=settings.forecast_horizon,
        ge=1,
        le=360,
        description="Number of future periods to forecast",
    )


class ForecastResponse(BaseModel):
    source: str
    model: str
    periods: int
    forecast: list[dict]  # [{ds, yhat, yhat_lower, yhat_upper}, ...]


class ScoreRequest(BaseModel):
    model: str = Field(default="sklearn-logreg", description="PD model key")
    loans: list[dict[str, Any]] = Field(
        ..., description="List of loan feature dicts matching the training schema"
    )


class ScoreResponse(BaseModel):
    model: str
    n_loans: int
    scores: list[float]  # PD probabilities in [0, 1]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/forecast", response_model=ForecastResponse)
async def forecast(req: ForecastRequest) -> ForecastResponse:
    """Generate a time-series delinquency-rate forecast using a Prophet artifact.

    The artifact must exist in ``models/artifacts/prophet.joblib`` — run
    ``pmai train --model prophet`` first.
    """

    log.info("Forecast request: source={} model={} horizon={}", req.source, req.model, req.horizon)

    try:
        from models.registry import load as load_model
        artifact = load_model(req.model)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Model artifact '{req.model}' not found. Run `pmai train --model {req.model}` first.",
        ) from exc

    # Artifact is either a Prophet model directly or a dict wrapper
    prophet_model = artifact if not isinstance(artifact, dict) else artifact.get("model")
    if prophet_model is None:
        raise HTTPException(
            status_code=422,
            detail=f"Artifact '{req.model}' is not a Prophet model. Use model='prophet'.",
        )

    try:
        future = prophet_model.make_future_dataframe(periods=req.horizon, freq="MS")
        fc_df = prophet_model.predict(future)
    except Exception as exc:
        log.error("Prophet forecast failed: {}", exc)
        raise HTTPException(status_code=500, detail=f"Forecast failed: {exc}") from exc

    # Return only the future periods (beyond training data)
    future_fc = fc_df.tail(req.horizon)[["ds", "yhat", "yhat_lower", "yhat_upper"]].copy()
    future_fc["ds"] = future_fc["ds"].dt.strftime("%Y-%m-%d")
    # Clip predictions to valid probability range [0, 1]
    for col in ("yhat", "yhat_lower", "yhat_upper"):
        future_fc[col] = future_fc[col].clip(0, 1).round(6)

    records = future_fc.to_dict(orient="records")
    log.info("Forecast complete: {} periods returned", len(records))

    return ForecastResponse(
        source=req.source,
        model=req.model,
        periods=len(records),
        forecast=records,
    )


@app.post("/score", response_model=ScoreResponse)
async def score(req: ScoreRequest) -> ScoreResponse:
    """Score a batch of loans using a saved PD model artifact.

    Returns one probability-of-default score per loan, in [0, 1].
    """
    import pandas as pd

    log.info("Score request: model={} n_loans={}", req.model, len(req.loans))

    if not req.loans:
        raise HTTPException(status_code=422, detail="loans list must not be empty")

    try:
        from models.registry import load as load_model
        artifact = load_model(req.model)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Model artifact '{req.model}' not found. Run `pmai train --model {req.model}` first.",
        ) from exc

    if not isinstance(artifact, dict) or "pipeline" not in artifact:
        raise HTTPException(
            status_code=422,
            detail=f"Artifact '{req.model}' is not a sklearn PD model. Use model='sklearn-logreg' or 'sklearn-rf'.",
        )

    pipeline = artifact["pipeline"]
    feature_cols: list[str] = artifact.get("feature_cols", [])

    try:
        df = pd.DataFrame(req.loans)
        # Ensure all expected feature columns exist (fill missing with NaN)
        for col in feature_cols:
            if col not in df.columns:
                df[col] = float("nan")
        X = df[feature_cols]
        scores = pipeline.predict_proba(X)[:, 1].round(6).tolist()
    except Exception as exc:
        log.error("Scoring failed: {}", exc)
        raise HTTPException(status_code=500, detail=f"Scoring failed: {exc}") from exc

    log.info("Scoring complete: {} loans scored", len(scores))
    return ScoreResponse(model=req.model, n_loans=len(scores), scores=scores)
