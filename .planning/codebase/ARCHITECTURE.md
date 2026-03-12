# Architecture

**Analysis Date:** 2026-03-12

## Pattern Overview

**Overall:** Layered pipeline architecture with CLI orchestration, batch/streaming processing stages, and HTTP API service layer.

**Key Characteristics:**
- Command-line driven data pipeline (ingest → feature engineering → training → forecasting)
- Modular feature engineering pipeline with plugin registry and YAML configuration
- Dual-model approach: Prophet for time-series forecasting, sklearn classifiers for probability-of-default (PD) scoring
- Model versioning and registry with active-model aliasing
- Job-based asynchronous task queue for long-running operations (training, monitoring, pipeline)
- Monitoring package for drift detection and performance tracking
- Multi-tenant support with user-namespaced model registries

## Layers

**Configuration Layer:**
- Purpose: Centralized settings management via Pydantic BaseSettings
- Location: `config/settings.py`
- Contains: Path configuration, API settings, auth tokens, MLflow URIs, FRED API keys
- Depends on: Environment variables (`.env`)
- Used by: All downstream modules

**Data Ingestion Layer:**
- Purpose: Load data from multiple sources (Fannie Mae origination/performance files, FRED API, CSV/Parquet)
- Location: `data_ingestion/`
- Contains: `loader.py` (façade), `ingest_fannie.py`, `ingest_fred.py`, `seed_demo.py`
- Depends on: Config (settings, data paths), external APIs (FRED)
- Used by: CLI (`main.py`), training pipeline, demo seeding

**Feature Engineering Layer:**
- Purpose: Transform raw data into engineered features via registered function pipeline
- Location: `features/`
- Contains: `engineer.py` (CLI delegate), `build_features.py` (orchestrator), `feature_defs.py` (registry), `labels.py`, `macro_join.py`
- Depends on: Ingested data, feature definitions YAML (`config/features.yaml`)
- Used by: Training pipeline, model development
- Key Design: Features grouped by source (origination, performance, macro) and run in dependency order. Leakage guard enforced via `shift(1)` and proper temporal ordering.

**Model Training Layer:**
- Purpose: Train three model types (Prophet forecaster, sklearn Logistic Regression, Random Forest) with MLflow tracking
- Location: `training/`
- Contains: `trainer.py` (orchestrator), `train_baseline.py`, `train_xgb.py`, `calibration.py`, `split.py`, `interpretability.py`
- Depends on: Feature data, feature definitions, training config (`config/training.yaml`)
- Used by: CLI, API job endpoints, demo seeding
- Key Design: Supports `DemoTrendForecaster` as fallback when Prophet fails in low-memory mode. All models logged to MLflow with metadata.

**Model Registry & Artifact Management:**
- Purpose: Version control and activation of trained models using joblib serialization
- Location: `models/registry.py`
- Contains: Local file-based registry with manifest JSON, version tracking, SHA256 checksums
- Depends on: Job configuration, joblib
- Used by: Training, service, monitoring
- Key Design: Supports global and user-namespaced registries; "current.joblib" is active-model alias

**Service Layer (FastAPI):**
- Purpose: HTTP API for prediction, model management, job submission, and monitoring
- Location: `service/`
- Contains: `api.py` (main endpoints), `model_loader.py` (scoring), `auth.py`, `jobs.py`, `schemas.py`
- Depends on: Config, models registry, monitoring package, training module
- Used by: External clients, demo UI
- Key Features:
  - Three prediction endpoints: `/forecast` (time-series), `/score` (PD), `/batch-score` (multiple PD predictions)
  - Job management: `/jobs/train`, `/jobs/pipeline`, `/jobs/monitor`, `/jobs/seed-demo` (async, 202 Accepted)
  - User-scoped endpoints: `/me/*` for authenticated users (separate namespace, auth via JWT)
  - Model catalog: `/models`, `/models/active`, `/models/{name}/versions`, `/models/activate`
  - Monitoring: `/monitoring/summary`, `/jobs/monitor`
  - Auth: `/auth/register`, `/auth/login`, `/auth/me`
  - Health: `/health`, `/ready`

**Monitoring Layer:**
- Purpose: Drift detection (feature drift, score drift, performance drift) and health reporting
- Location: `monitoring/`
- Contains: `__init__.py` (orchestrator), `drift.py`, `score_drift.py`, `perf_drift.py`, `metrics.py`
- Depends on: Pandas, reference/current datasets
- Used by: CLI, API job endpoints
- Key Design: Computes PSI, KS statistics, rolling AUC, and generates Markdown summary reports

**Utilities:**
- Purpose: Cross-cutting logging
- Location: `utils/logging.py`
- Contains: Structured logging configuration with optional JSON serialization
- Depends on: Python structlog
- Used by: All modules

## Data Flow

**Ingest → Features → Train → Serve:**

1. User invokes CLI: `pmai ingest --source fannie-mae`
2. `main.ingest()` calls `data_ingestion.loader.load(source)` → DataFrame
3. DataFrame persisted to `data/raw/fannie_mae/origination/*.parquet`
4. User invokes: `pmai features --source fannie-mae`
5. `main.features()` calls `features.engineer.build_features(source)`
6. Feature engineering reads raw parquet, applies registry functions in order
7. Output written to `data/processed/fannie_mae/features/*.parquet`
8. User invokes: `pmai train --model sklearn-rf`
9. `main.train()` calls `training.trainer.train_model(model_name)`
10. Trainer reads features parquet, splits data, trains model, logs run to MLflow
11. Model artifact saved via `models.registry.save()`
12. User invokes: `pmai serve`
13. FastAPI server starts, loads active model at startup via `service.model_loader.model.load()`
14. Incoming `/score` or `/forecast` requests routed to appropriate predictor

**Async Job Queue:**

1. Client POSTs to `/jobs/train`, `/jobs/pipeline`, etc.
2. `service.jobs.job_manager.submit(JobType, request_payload)` → job_id
3. Job queued in memory with status "pending"
4. Background thread picks up job, executes handler (e.g., `_run_train_job()`)
5. Job transitions: pending → started → completed/failed
6. Client polls `/jobs/{job_id}` to check status

**State Management:**

- **Configuration State:** Loaded once at app startup from `config/settings.py`
- **Model State:** Loaded once at API startup; reloadable via activation endpoint
- **Job State:** In-memory dict keyed by UUID (lost on restart; not persistent)
- **Data State:** Persisted to disk (parquet files under `data/`)
- **Registry State:** Persisted to disk (manifest JSON under `models/artifacts/`)

## Key Abstractions

**Data Source Abstraction:**
- Purpose: Support multiple data inputs (Fannie Mae, FRED, CSV, Parquet)
- Examples: `data_ingestion/loader.py` routes via string prefix (`csv:`, `parquet:`, source names)
- Pattern: Source-specific loaders are lazy-imported only when needed

**Feature Registry:**
- Purpose: Declarative feature function composition
- Examples: `features/feature_defs.py` defines `REGISTRY[group][feature_name] = callable`
- Pattern: Functions grouped by source (origination, performance, macro) with dependency ordering

**Model Abstraction:**
- Purpose: Support multiple model types with unified interface
- Examples: Prophet (time-series), LogisticRegression, RandomForest all wrapped as joblib artifacts
- Pattern: Trainer detects model type by name prefix and delegates to specialized trainer; service extracts `predict_proba` interface uniformly

**Scorer Abstraction:**
- Purpose: Unified prediction + explanation interface
- Examples: `service.model_loader.ModelLoader` handles loading, feature alignment, probability extraction, SHAP factor extraction
- Pattern: Supports linear models (coefficient-based) and tree models (SHAP-based) with fallback to linear factors

## Entry Points

**CLI Entry:**
- Location: `main.py`
- Triggers: `python -m main <command>`
- Responsibilities: Parse args, setup logging, delegate to subcommand handlers (ingest, features, train, serve, pipeline, monitor)

**Service Entry:**
- Location: `service/api.py`
- Triggers: `pmai serve` or `uvicorn service.api:app`
- Responsibilities: FastAPI app initialization, lifespan hooks (init DB, load models), route handlers

**Training Entry:**
- Location: `training/trainer.py`
- Triggers: `train_model(model_name)` from CLI or API
- Responsibilities: Load features, split data, train model, log metrics to MLflow, save artifact

## Error Handling

**Strategy:** Exception propagation with logging at each layer; API wraps in HTTPException for HTTP responses.

**Patterns:**
- **File not found:** Raised as `FileNotFoundError` with descriptive message; caught in API and returned 404
- **Invalid source key:** Raised as `ValueError` in `data_ingestion.loader.load()`; descriptive message lists supported keys
- **Model artifact missing:** Handled gracefully with fallback (e.g., `DemoTrendForecaster` when Prophet unavailable)
- **Validation:** Pydantic schemas validate request payloads; invalid payloads return 422 Unprocessable Entity
- **Auth:** Invalid token returns 401 Unauthorized; missing token returns 403 Forbidden

## Cross-Cutting Concerns

**Logging:** Configured globally in `config.settings` and `utils.logging`. All modules use `from utils.logging import log` and call `log.info()`, `log.warning()`, etc. Optional JSON serialization for production.

**Validation:** Pydantic `BaseModel` for all request/response schemas and settings. Type hints throughout.

**Authentication:** JWT tokens issued by `/auth/login`, decoded by `_require_user()` dependency for `/me/*` endpoints. User namespace isolation via `namespace` parameter to registry.

**MLflow Tracking:** All training runs logged to MLflow (URI in settings). Experiments grouped by name; runs track model type, AUC, metrics, params.

---

*Architecture analysis: 2026-03-12*
