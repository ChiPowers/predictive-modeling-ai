from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Factor(BaseModel):
    name: str
    value: float = Field(description="SHAP value (positive = increases default risk)")


class ScoreRequest(BaseModel):
    features: dict[str, Any] = Field(
        description="Loan feature key-value pairs",
        examples=[
            {
                "credit_score": 720,
                "original_ltv": 80.0,
                "original_dti": 35.0,
                "original_interest_rate": 6.5,
                "original_loan_amount": 350000,
                "loan_purpose": "P",
                "property_type": "SF",
                "num_borrowers": 2,
            }
        ],
    )
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Decision threshold: pd >= threshold → 'default'",
    )


class ScoreResponse(BaseModel):
    pd: float = Field(ge=0.0, le=1.0, description="Predicted probability of default")
    decision: str = Field(description="'default' or 'current'")
    top_factors: list[Factor] = Field(description="Top drivers (by |SHAP value|), descending")


class BatchScoreRequest(BaseModel):
    records: list[ScoreRequest] = Field(min_length=1)


class BatchScoreResponse(BaseModel):
    results: list[ScoreResponse]
    count: int


class ModelArtifactStatus(BaseModel):
    name: str
    path: str
    exists: bool


class ApiMetadataResponse(BaseModel):
    app_name: str
    version: str
    mode: str
    capabilities: dict[str, list[str]]
    artifacts: list[ModelArtifactStatus]
    monitoring_available: bool


class MonitoringSummaryResponse(BaseModel):
    available: bool
    summary_markdown: str | None = None
    drift_features: dict[str, Any] | None = None
    score_drift: dict[str, Any] | None = None
    perf_drift: dict[str, Any] | None = None


class TrainJobRequest(BaseModel):
    model: str = Field(default="sklearn-rf")
    run_name: str | None = None
    experiment_name: str | None = None


class PipelineJobRequest(BaseModel):
    source: str = Field(default="fannie-mae")
    model: str = Field(default="sklearn-rf")
    run_name: str | None = None
    experiment_name: str | None = None


class MonitorJobRequest(BaseModel):
    reference_path: str
    current_path: str
    score_ref_col: str = Field(default="pd_score")
    score_cur_col: str = Field(default="pd_score")
    label_col: str = Field(default="default_flag")
    period_col: str = Field(default="monthly_reporting_period")
    output_dir: str = Field(default="reports/monitoring")
    window: int = Field(default=3, ge=1)
    auc_threshold: float = Field(default=0.65, ge=0.0, le=1.0)


class SeedDemoJobRequest(BaseModel):
    output_dir: str = Field(default="data/raw/fannie_mae/combined")
    filename: str = Field(default="demo_2025Q1.csv")
    n_loans: int = Field(default=120, ge=40, le=4000)
    months: int = Field(default=6, ge=4, le=24)
    seed: int = Field(default=42)
    overwrite: bool = Field(default=True)


class JobStatusResponse(BaseModel):
    id: str
    job_type: str
    status: str
    created_at: str
    started_at: str | None
    finished_at: str | None
    input_payload: dict[str, Any]
    result: dict[str, Any] | list[Any] | str | int | float | bool | None
    error: str | None


class JobListResponse(BaseModel):
    jobs: list[JobStatusResponse]


class ModelEntryResponse(BaseModel):
    name: str
    version_count: int
    latest_version_id: str | None


class ModelVersionResponse(BaseModel):
    name: str
    version_id: str
    created_at: str
    artifact_path: str
    artifact_filename: str
    sha256: str
    metadata: dict[str, Any]


class ModelCatalogResponse(BaseModel):
    models: list[ModelEntryResponse]
    active: dict[str, Any] | None


class ActivateModelRequest(BaseModel):
    name: str
    version_id: str | None = None


class ActiveModelResponse(BaseModel):
    name: str
    version_id: str
    artifact_path: str
    current_alias_path: str
    updated_at: str


class AuthRegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)


class AuthLoginRequest(BaseModel):
    username: str
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class AuthMeResponse(BaseModel):
    username: str


class InterpretRequest(BaseModel):
    context_type: Literal["score", "forecast", "monitoring", "batch"]
    data: dict[str, Any] = Field(description="Raw model output to interpret")


class InterpretResponse(BaseModel):
    narrative: str = Field(description="Plain-language AI interpretation")
