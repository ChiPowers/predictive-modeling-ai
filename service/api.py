"""FastAPI prediction service."""
from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import anthropic
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config.settings import settings
from models import registry as model_registry
from models.registry import load as load_model
from monitoring import run_monitoring_job
from service.auth import authenticate_user, decode_token, init_db, issue_token, register_user
from service.jobs import job_manager
from service.model_loader import model as scoring_model
from service.schemas import (
    ActivateModelRequest,
    ActiveModelResponse,
    ApiMetadataResponse,
    AuthLoginRequest,
    AuthMeResponse,
    AuthRegisterRequest,
    AuthTokenResponse,
    BatchScoreRequest,
    BatchScoreResponse,
    InterpretRequest,
    InterpretResponse,
    JobListResponse,
    JobStatusResponse,
    ModelArtifactStatus,
    ModelCatalogResponse,
    ModelEntryResponse,
    ModelVersionResponse,
    MonitoringSummaryResponse,
    MonitorJobRequest,
    PipelineJobRequest,
    ScoreRequest,
    ScoreResponse,
    SeedDemoJobRequest,
    TrainJobRequest,
)
from training.trainer import PROPHET_FORECAST_COLS
from utils.logging import configure_logging, log

_FORECAST_CACHE: dict[str, Any] = {}
_ANTHROPIC_CLIENT: anthropic.AsyncAnthropic | None = None
_MONITORING_DIR = Path("reports/monitoring")
_MODEL_NAMES = ("prophet", "sklearn-logreg", "sklearn-rf")
_APP_NAME = "predictive-modeling-ai"
_APP_VERSION = "0.1.0"
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_AUTH_BEARER = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # noqa: ARG001
    configure_logging(level=settings.log_level, serialize=settings.log_serialize)
    log.info("API starting up")
    init_db()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY not set — POST /ai/interpret will return 503 on auth failure")
    try:
        scoring_model.load()
    except FileNotFoundError as exc:
        log.warning("Scoring model artifact not found at startup: {}", exc)
    yield
    log.info("API shutting down")


app = FastAPI(
    title="Predictive Modeling AI",
    description="Forecast + PD scoring API",
    version=_APP_VERSION,
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")


class ForecastRequest(BaseModel):
    source: str = Field(description="Dataset source label for metadata echo.")
    model: str = Field(default="prophet", description="Forecast model key.")
    horizon: int = Field(default=settings.forecast_horizon, ge=1, le=120)


class ForecastResponse(BaseModel):
    source: str
    model: str
    periods: int
    forecast: list[dict[str, Any]]


def _get_forecast_model(model_name: str) -> Any:
    if model_name in _FORECAST_CACHE:
        return _FORECAST_CACHE[model_name]
    loaded = load_model(model_name)
    _FORECAST_CACHE[model_name] = loaded
    return loaded


def _get_anthropic_client() -> anthropic.AsyncAnthropic:
    global _ANTHROPIC_CLIENT
    if _ANTHROPIC_CLIENT is None:
        _ANTHROPIC_CLIENT = anthropic.AsyncAnthropic()
        # SDK reads ANTHROPIC_API_KEY from environment automatically
    return _ANTHROPIC_CLIENT


def _is_real_data_mode() -> bool:
    orig_dir = Path("data/raw/fannie_mae/origination")
    perf_dir = Path("data/raw/fannie_mae/performance")
    has_orig = any(orig_dir.glob("Acquisition_*.txt"))
    has_perf = any(perf_dir.glob("Performance_*.txt"))
    return has_orig and has_perf


def _artifact_statuses() -> list[ModelArtifactStatus]:
    return [
        ModelArtifactStatus(
            name=name,
            path=str(settings.models_dir / f"{name}.joblib"),
            exists=(settings.models_dir / f"{name}.joblib").exists(),
        )
        for name in _MODEL_NAMES
    ]


def _load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _run_train_job(req: TrainJobRequest) -> dict[str, Any]:
    from training.trainer import train_model

    artifact_path = train_model(
        req.model,
        run_name=req.run_name,
        experiment_name=req.experiment_name,
    )
    return {"artifact_path": str(artifact_path), "model": req.model}


def _run_pipeline_job(req: PipelineJobRequest) -> dict[str, Any]:
    from data_ingestion.loader import load
    from features.engineer import build_features
    from training.trainer import train_model

    load(req.source)
    feature_groups = ["origination", "macro_stub"] if settings.low_memory_mode else None
    feature_df = build_features(req.source, groups=feature_groups)
    artifact_path = train_model(
        req.model,
        run_name=req.run_name,
        experiment_name=req.experiment_name,
    )
    return {
        "source": req.source,
        "model": req.model,
        "feature_rows": len(feature_df),
        "artifact_path": str(artifact_path),
    }


def _run_train_job_user(req: TrainJobRequest, username: str) -> dict[str, Any]:
    from training.trainer import train_model

    artifact_path = train_model(
        req.model,
        run_name=req.run_name,
        experiment_name=req.experiment_name,
        namespace=username,
    )
    return {"artifact_path": str(artifact_path), "model": req.model, "namespace": username}


def _run_monitor_job(req: MonitorJobRequest) -> dict[str, Any]:
    ref_df = pd.read_parquet(req.reference_path)
    cur_df = pd.read_parquet(req.current_path)

    score_ref = ref_df[req.score_ref_col] if req.score_ref_col in ref_df.columns else pd.Series(dtype=float)
    score_cur = cur_df[req.score_cur_col] if req.score_cur_col in cur_df.columns else pd.Series(dtype=float)
    labels = cur_df[req.label_col] if req.label_col in cur_df.columns else None
    period = cur_df[req.period_col] if req.period_col in cur_df.columns else None
    auc_scores = score_cur if labels is not None else None

    results = run_monitoring_job(
        feature_ref=ref_df,
        feature_cur=cur_df,
        score_ref=score_ref,
        score_cur=score_cur,
        labels=labels,
        scores=auc_scores,
        period_col=period,
        output_dir=Path(req.output_dir),
        window=req.window,
        auc_alert_threshold=req.auc_threshold,
    )

    return {
        "output_dir": req.output_dir,
        "reference_rows": len(ref_df),
        "current_rows": len(cur_df),
        "score_alert": bool(results.get("score_drift", {}).get("alert", False)),
    }


def _run_seed_demo_job(req: SeedDemoJobRequest) -> dict[str, Any]:
    from data_ingestion.seed_demo import seed_demo_data

    return seed_demo_data(
        output_dir=req.output_dir,
        filename=req.filename,
        n_loans=req.n_loans,
        months=req.months,
        seed=req.seed,
        overwrite=req.overwrite,
    )


def _build_prompt(context_type: str, data: dict[str, Any]) -> str:
    if context_type == "score":
        pd_val = data.get("pd", 0.0)
        decision = data.get("decision", "unknown")
        factors = data.get("top_factors", [])
        if factors:
            factor_str = ", ".join(
                f["name"] if isinstance(f, dict) else getattr(f, "name", str(f))
                for f in factors[:3]
            )
            factor_clause = f" Top risk factors: {factor_str}."
        else:
            factor_clause = ""
        return (
            f"A mortgage loan was scored. Default probability: {pd_val:.0%}. "
            f"Decision: {decision}.{factor_clause} "
            "Write a 2-3 sentence plain-language interpretation for a non-technical reader. "
            "Include a recommended action."
        )
    elif context_type == "forecast":
        forecast_rows = data.get("forecast", [])
        threshold = data.get("threshold", 0.20)
        exceed = [r for r in forecast_rows if isinstance(r, dict) and r.get("yhat", 0) >= threshold]
        first_exceed = exceed[0].get("ds", "unknown") if exceed else None
        if first_exceed:
            return (
                f"A delinquency forecast was run over {len(forecast_rows)} months. "
                f"The alert threshold is {threshold:.2f}. "
                f"{len(exceed)} of {len(forecast_rows)} periods breach the threshold. "
                f"First exceedance: {first_exceed}. "
                "Write a 2-3 sentence plain-language interpretation with a recommended action."
            )
        else:
            return (
                f"A delinquency forecast was run over {len(forecast_rows)} months. "
                f"The alert threshold is {threshold:.2f}. No periods breach the threshold. "
                "Write a 2-3 sentence plain-language summary confirming the portfolio looks stable."
            )
    elif context_type == "monitoring":
        drift_features = data.get("drift_features") or {}
        score_drift = data.get("score_drift") or {}
        perf_drift = data.get("perf_drift") or {}
        score_alert = score_drift.get("alert", False)
        auc = perf_drift.get("auc", None)
        high_drift = [k for k, v in drift_features.items() if isinstance(v, dict) and v.get("psi", 0) > 0.2]
        auc_clause = f" AUC: {auc:.2f}." if auc is not None else ""
        alert_clause = " Score distribution alert is active." if score_alert else ""
        drift_clause = f" High-drift features: {', '.join(high_drift)}." if high_drift else " No features show high drift."
        return (
            f"Model monitoring results: {len(drift_features)} features analyzed.{drift_clause}{alert_clause}{auc_clause} "
            "Write a 2-3 sentence plain-language status summary and state whether retraining is recommended."
        )
    elif context_type == "batch":
        results = data.get("results", [])
        count = len(results)
        high_risk = sum(1 for r in results if r.get("pd", 0) >= 0.50)
        avg_pd = sum(r.get("pd", 0) for r in results) / count if count else 0
        return (
            f"A portfolio of {count} loans was scored. "
            f"Average default probability: {avg_pd:.0%}. "
            f"{high_risk} of {count} loans are high-risk (PD >= 50%). "
            "Write a 2-3 sentence plain-language portfolio summary. "
            "Include a concrete recommended action for the portfolio manager."
        )
    else:
        return f"Interpret the following model output: {data}"


def _extract_predictor(model_obj: Any) -> Any:
    if isinstance(model_obj, dict) and "pipeline" in model_obj:
        return model_obj["pipeline"]
    return model_obj


def _score_with_model(model_obj: Any, features: dict[str, Any], threshold: float) -> ScoreResponse:
    predictor = _extract_predictor(model_obj)
    if not hasattr(predictor, "predict_proba"):
        raise ValueError("Loaded model does not support predict_proba")

    frame = pd.DataFrame([features])
    if isinstance(model_obj, dict) and isinstance(model_obj.get("feature_cols"), list):
        frame = frame.reindex(columns=model_obj["feature_cols"])
    probs = predictor.predict_proba(frame)[:, 1]
    pd_score = float(probs[0])
    decision = "default" if pd_score >= threshold else "current"
    return ScoreResponse(pd=pd_score, decision=decision, top_factors=[])


def _require_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_AUTH_BEARER),  # noqa: B008
) -> str:
    if not settings.auth_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Auth disabled")
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    username = str(payload.get("sub", "")).strip()
    if not username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    return username


@app.get("/", include_in_schema=False)
async def ui_index() -> FileResponse:
    """Serve the frontend MVP."""
    return FileResponse(_STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "model_loaded": scoring_model.is_loaded}


@app.get("/ready", tags=["ops"])
async def ready() -> JSONResponse:
    """Readiness probe for deployment orchestrators.

    Ready means scoring model is loaded and the model artifact directory exists.
    """
    checks = {
        "model_loaded": scoring_model.is_loaded,
        "models_dir_exists": settings.models_dir.exists(),
        "active_model_set": model_registry.get_active() is not None,
    }
    is_ready = checks["model_loaded"] and checks["models_dir_exists"]
    payload = {"status": "ready" if is_ready else "not_ready", "checks": checks}
    return JSONResponse(status_code=200 if is_ready else 503, content=payload)


@app.post("/auth/register", status_code=status.HTTP_201_CREATED, tags=["auth"])
async def auth_register(req: AuthRegisterRequest) -> dict[str, str]:
    try:
        register_user(req.username, req.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return {"status": "registered"}


@app.post("/auth/login", response_model=AuthTokenResponse, tags=["auth"])
async def auth_login(req: AuthLoginRequest) -> AuthTokenResponse:
    if not authenticate_user(req.username, req.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return AuthTokenResponse(access_token=issue_token(req.username), username=req.username)


@app.get("/auth/me", response_model=AuthMeResponse, tags=["auth"])
async def auth_me(username: str = Depends(_require_user)) -> AuthMeResponse:
    return AuthMeResponse(username=username)


@app.get("/metadata", response_model=ApiMetadataResponse, tags=["ops"])
async def metadata() -> ApiMetadataResponse:
    """Frontend contract endpoint for environment and capability discovery."""
    mode = "real-data" if _is_real_data_mode() else "demo"
    summary_path = _MONITORING_DIR / "summary.md"
    return ApiMetadataResponse(
        app_name=_APP_NAME,
        version=_APP_VERSION,
        mode=mode,
        capabilities={
            "ingest_sources": ["fannie-mae", "fred", "csv:<path>", "parquet:<path>"],
            "train_models": ["prophet", "sklearn-logreg", "sklearn-rf"],
            "forecast_models": ["prophet"],
            "score_endpoints": ["/score", "/batch_score"],
            "job_endpoints": ["/jobs/seed-demo", "/jobs/train", "/jobs/pipeline", "/jobs/monitor"],
            "model_endpoints": ["/models", "/models/active", "/models/{name}/versions"],
        },
        artifacts=_artifact_statuses(),
        monitoring_available=summary_path.exists(),
    )


@app.get("/monitoring/summary", response_model=MonitoringSummaryResponse, tags=["monitoring"])
async def monitoring_summary() -> MonitoringSummaryResponse:
    """Return the latest monitoring reports for frontend rendering."""
    summary_path = _MONITORING_DIR / "summary.md"
    drift_path = _MONITORING_DIR / "drift_features.json"
    score_path = _MONITORING_DIR / "score_drift.json"
    perf_path = _MONITORING_DIR / "perf_drift.json"

    summary_md = summary_path.read_text() if summary_path.exists() else None
    drift_features = _load_json_if_exists(drift_path)
    score_drift = _load_json_if_exists(score_path)
    perf_drift = _load_json_if_exists(perf_path)
    available = any([summary_md, drift_features, score_drift, perf_drift])
    return MonitoringSummaryResponse(
        available=available,
        summary_markdown=summary_md,
        drift_features=drift_features,
        score_drift=score_drift,
        perf_drift=perf_drift,
    )


@app.post("/jobs/train", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED, tags=["jobs"])
async def submit_train_job(req: TrainJobRequest) -> JobStatusResponse:
    """Submit a background training job."""
    job = job_manager.submit("train", req.model_dump(), lambda: _run_train_job(req))
    return JobStatusResponse(**job)


@app.post("/jobs/pipeline", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED, tags=["jobs"])
async def submit_pipeline_job(req: PipelineJobRequest) -> JobStatusResponse:
    """Submit a background ingest->features->train pipeline job."""
    job = job_manager.submit("pipeline", req.model_dump(), lambda: _run_pipeline_job(req))
    return JobStatusResponse(**job)


@app.post("/jobs/monitor", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED, tags=["jobs"])
async def submit_monitor_job(req: MonitorJobRequest) -> JobStatusResponse:
    """Submit a background monitoring job."""
    job = job_manager.submit("monitor", req.model_dump(), lambda: _run_monitor_job(req))
    return JobStatusResponse(**job)


@app.post("/jobs/seed-demo", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED, tags=["jobs"])
async def submit_seed_demo_job(req: SeedDemoJobRequest) -> JobStatusResponse:
    """Submit a background synthetic data generation job for demo environments."""
    job = job_manager.submit("seed-demo", req.model_dump(), lambda: _run_seed_demo_job(req))
    return JobStatusResponse(**job)


@app.get("/jobs", response_model=JobListResponse, tags=["jobs"])
async def list_jobs(limit: int = 50) -> JobListResponse:
    jobs = job_manager.list(limit=limit)
    return JobListResponse(jobs=[JobStatusResponse(**j) for j in jobs])


@app.get("/jobs/{job_id}", response_model=JobStatusResponse, tags=["jobs"])
async def get_job(job_id: str) -> JobStatusResponse:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobStatusResponse(**job)


@app.post("/me/jobs/train", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED, tags=["me"])
async def submit_my_train_job(req: TrainJobRequest, username: str = Depends(_require_user)) -> JobStatusResponse:
    job = job_manager.submit(
        "train",
        req.model_dump(),
        lambda: _run_train_job_user(req, username),
        owner=username,
    )
    return JobStatusResponse(**job)


@app.post("/me/jobs/seed-demo", response_model=JobStatusResponse, status_code=status.HTTP_202_ACCEPTED, tags=["me"])
async def submit_my_seed_demo_job(
    req: SeedDemoJobRequest,
    username: str = Depends(_require_user),
) -> JobStatusResponse:
    job = job_manager.submit(
        "seed-demo",
        req.model_dump(),
        lambda: _run_seed_demo_job(req),
        owner=username,
    )
    return JobStatusResponse(**job)


@app.get("/me/jobs", response_model=JobListResponse, tags=["me"])
async def list_my_jobs(limit: int = 50, username: str = Depends(_require_user)) -> JobListResponse:
    jobs = job_manager.list(limit=limit, owner=username)
    return JobListResponse(jobs=[JobStatusResponse(**j) for j in jobs])


@app.get("/me/jobs/{job_id}", response_model=JobStatusResponse, tags=["me"])
async def get_my_job(job_id: str, username: str = Depends(_require_user)) -> JobStatusResponse:
    job = job_manager.get(job_id, owner=username)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobStatusResponse(**job)


@app.get("/models", response_model=ModelCatalogResponse, tags=["models"])
async def list_models() -> ModelCatalogResponse:
    items = [ModelEntryResponse(**m) for m in model_registry.list_models()]
    return ModelCatalogResponse(models=items, active=model_registry.get_active())


@app.get("/models/active", response_model=ActiveModelResponse, tags=["models"])
async def get_active_model() -> ActiveModelResponse:
    active = model_registry.get_active()
    if active is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active model")
    return ActiveModelResponse(**active)


@app.get("/models/{name}/versions", response_model=list[ModelVersionResponse], tags=["models"])
async def list_model_versions(name: str) -> list[ModelVersionResponse]:
    versions = model_registry.get_versions(name)
    return [ModelVersionResponse(**v) for v in versions]


@app.post("/models/activate", response_model=ActiveModelResponse, tags=["models"])
async def activate_model(req: ActivateModelRequest) -> ActiveModelResponse:
    try:
        active = model_registry.activate(req.name, req.version_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    try:
        current_alias = Path(active["current_alias_path"])
        scoring_model.load(current_alias.parent, current_alias.name)
    except Exception as exc:  # noqa: BLE001
        log.warning("Activated model but could not reload scoring runtime: {}", exc)
    return ActiveModelResponse(**active)


@app.get("/me/models", response_model=ModelCatalogResponse, tags=["me"])
async def list_my_models(username: str = Depends(_require_user)) -> ModelCatalogResponse:
    items = [ModelEntryResponse(**m) for m in model_registry.list_models(namespace=username)]
    return ModelCatalogResponse(models=items, active=model_registry.get_active(namespace=username))


@app.get("/me/models/{name}/versions", response_model=list[ModelVersionResponse], tags=["me"])
async def list_my_model_versions(name: str, username: str = Depends(_require_user)) -> list[ModelVersionResponse]:
    versions = model_registry.get_versions(name, namespace=username)
    return [ModelVersionResponse(**v) for v in versions]


@app.post("/me/models/activate", response_model=ActiveModelResponse, tags=["me"])
async def activate_my_model(
    req: ActivateModelRequest,
    username: str = Depends(_require_user),
) -> ActiveModelResponse:
    try:
        active = model_registry.activate(req.name, req.version_id, namespace=username)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ActiveModelResponse(**active)


@app.get("/me/models/active", response_model=ActiveModelResponse, tags=["me"])
async def get_my_active_model(username: str = Depends(_require_user)) -> ActiveModelResponse:
    active = model_registry.get_active(namespace=username)
    if active is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active model")
    return ActiveModelResponse(**active)


@app.post("/forecast", response_model=ForecastResponse)
async def forecast(req: ForecastRequest) -> ForecastResponse:
    """Return forward forecast rows from a trained Prophet artifact."""
    log.info("Forecast request: source={} model={} horizon={}", req.source, req.model, req.horizon)

    if req.model != "prophet":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only model='prophet' is currently supported for /forecast.",
        )

    try:
        model_obj = _get_forecast_model(req.model)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Forecast model artifact not found: {exc}",
        ) from exc

    if not hasattr(model_obj, "make_future_dataframe") or not hasattr(model_obj, "predict"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Loaded artifact '{req.model}' is not a Prophet model.",
        )

    future = model_obj.make_future_dataframe(periods=req.horizon, freq="MS")
    pred = model_obj.predict(future)
    out = pred[PROPHET_FORECAST_COLS].tail(req.horizon).copy()
    out["ds"] = pd.to_datetime(out["ds"], errors="coerce").dt.strftime("%Y-%m-%d")
    forecast_rows = out.to_dict(orient="records")
    return ForecastResponse(
        source=req.source,
        model=req.model,
        periods=req.horizon,
        forecast=forecast_rows,
    )


@app.post(
    "/score",
    response_model=ScoreResponse,
    status_code=status.HTTP_200_OK,
    tags=["scoring"],
)
def score(request: ScoreRequest) -> ScoreResponse:
    """Score a single loan record."""
    if not scoring_model.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded. Check MODEL_ARTIFACT_DIR and MODEL_FILENAME.",
        )
    try:
        pd_score, decision, top_factors = scoring_model.score(
            request.features, threshold=request.threshold
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return ScoreResponse(pd=pd_score, decision=decision, top_factors=top_factors)


@app.post("/me/score", response_model=ScoreResponse, tags=["me"])
def score_me(request: ScoreRequest, username: str = Depends(_require_user)) -> ScoreResponse:
    try:
        model_obj = model_registry.load("current", namespace=username)
        return _score_with_model(model_obj, request.features, request.threshold)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@app.post(
    "/batch_score",
    response_model=BatchScoreResponse,
    status_code=status.HTTP_200_OK,
    tags=["scoring"],
)
def batch_score(request: BatchScoreRequest) -> BatchScoreResponse:
    """Score multiple records in a single request."""
    if not scoring_model.is_loaded:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded. Check MODEL_ARTIFACT_DIR and MODEL_FILENAME.",
        )
    try:
        raw_results = scoring_model.batch_score(
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


@app.post("/ai/interpret", response_model=InterpretResponse, tags=["ai"])
async def ai_interpret(req: InterpretRequest) -> InterpretResponse:
    """Call Claude to generate a plain-language narrative from model output."""
    try:
        client = _get_anthropic_client()
    except anthropic.AuthenticationError as exc:
        log.error("Claude client init failed (ANTHROPIC_API_KEY missing or invalid): {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI narrative unavailable: ANTHROPIC_API_KEY not configured",
        ) from exc
    prompt = _build_prompt(req.context_type, req.data)
    try:
        message = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system="You are a concise risk analyst writing for non-technical readers. Be direct and specific.",
            messages=[{"role": "user", "content": prompt}],
        )
        if message.content and hasattr(message.content[0], "text"):
            narrative = message.content[0].text
        else:
            narrative = "Interpretation unavailable."
    except anthropic.APIConnectionError as exc:
        log.error("Claude API connection error: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI narrative unavailable: service unreachable",
        ) from exc
    except anthropic.AuthenticationError as exc:
        log.error("Claude authentication error (check ANTHROPIC_API_KEY): {}", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI narrative unavailable: authentication failed",
        ) from exc
    except anthropic.RateLimitError as exc:
        log.warning("Claude rate limit hit: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI narrative unavailable: rate limited",
        ) from exc
    except anthropic.APIStatusError as exc:
        log.error("Claude API error {}: {}", exc.status_code, exc.message)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI narrative unavailable: upstream error {exc.status_code}",
        ) from exc
    return InterpretResponse(narrative=narrative)
