"""FastAPI prediction service."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from pydantic import BaseModel

from utils.logging import configure_logging, log
from config.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    configure_logging(level=settings.log_level, serialize=settings.log_serialize)
    log.info("API starting up")
    yield
    log.info("API shutting down")


app = FastAPI(
    title="Predictive Modeling AI",
    description="Historic and forecasted trend visualisation API",
    version="0.1.0",
    lifespan=lifespan,
)


class ForecastRequest(BaseModel):
    source: str
    model: str = "prophet"
    horizon: int = settings.forecast_horizon


class ForecastResponse(BaseModel):
    source: str
    model: str
    periods: int
    forecast: list[dict]  # [{ds, yhat, yhat_lower, yhat_upper}, ...]


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/forecast", response_model=ForecastResponse)
async def forecast(req: ForecastRequest) -> ForecastResponse:
    """Return a forecast for the requested source and model."""
    log.info("Forecast request: source={} model={} horizon={}", req.source, req.model, req.horizon)
    # TODO: load model artifact, run inference, return result
    raise NotImplementedError("Forecast endpoint not yet implemented")
