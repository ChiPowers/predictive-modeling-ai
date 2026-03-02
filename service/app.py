from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, status

from service.model_loader import model
from service.schemas import (
    BatchScoreRequest,
    BatchScoreResponse,
    Factor,
    ScoreRequest,
    ScoreResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load the model artifact at startup."""
    try:
        model.load()
    except FileNotFoundError as exc:
        # Allow the app to start without a model so /health still responds.
        # /score and /batch_score will return 503 until a model is present.
        import logging

        logging.warning("Model artifact not found at startup: %s", exc)
    yield


app = FastAPI(
    title="Predictive Modeling Scoring API",
    description="Returns probability of default (pd), a decision, and top SHAP-based factors.",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
def health() -> dict:
    """Liveness + model readiness check."""
    return {
        "status": "ok",
        "model_loaded": model.is_loaded,
        "timestamp": time.time(),
    }


# ---------------------------------------------------------------------------
# POST /score
# ---------------------------------------------------------------------------


@app.post(
    "/score",
    response_model=ScoreResponse,
    status_code=status.HTTP_200_OK,
    tags=["scoring"],
)
def score(request: ScoreRequest) -> ScoreResponse:
    """Score a single loan record and return pd, decision, and top factors."""
    if not model.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded. Check MODEL_ARTIFACT_DIR and MODEL_FILENAME.",
        )
    try:
        pd_score, decision, top_factors = model.score(
            request.features, threshold=request.threshold
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return ScoreResponse(pd=pd_score, decision=decision, top_factors=top_factors)


# ---------------------------------------------------------------------------
# POST /batch_score
# ---------------------------------------------------------------------------


@app.post(
    "/batch_score",
    response_model=BatchScoreResponse,
    status_code=status.HTTP_200_OK,
    tags=["scoring"],
)
def batch_score(request: BatchScoreRequest) -> BatchScoreResponse:
    """Score a batch of loan records in a single request."""
    if not model.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded. Check MODEL_ARTIFACT_DIR and MODEL_FILENAME.",
        )
    try:
        raw_results = model.batch_score(
            [(rec.features, rec.threshold) for rec in request.records]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    results = [
        ScoreResponse(pd=pd_score, decision=decision, top_factors=top_factors)
        for pd_score, decision, top_factors in raw_results
    ]
    return BatchScoreResponse(results=results, count=len(results))
