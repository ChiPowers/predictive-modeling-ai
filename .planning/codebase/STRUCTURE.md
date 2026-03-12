# Codebase Structure

**Analysis Date:** 2026-03-12

## Directory Layout

```
predictive-modeling-ai/
├── config/                      # Application settings and configuration files
│   ├── settings.py              # Pydantic BaseSettings (environment-driven config)
│   ├── data_paths.yaml          # Data directory paths
│   ├── features.yaml            # Feature engineering pipeline config
│   ├── training.yaml            # Model training hyperparameters
│   ├── mlflow.yaml              # MLflow tracking config
│   ├── fred.yaml                # FRED API source definitions
│   └── labeling.yaml            # Default labeling rules
├── data/                        # Data storage (not committed)
│   ├── raw/                     # Raw ingested data
│   │   └── fannie_mae/          # Fannie Mae origination/performance
│   │       ├── origination/
│   │       ├── performance/
│   │       └── combined/        # Demo seed data
│   └── processed/               # Feature-engineered data
│       └── fannie_mae/
│           ├── origination/
│           ├── performance/
│           └── features/        # Output of feature engineering
├── data_ingestion/              # Data loading and ingestion logic
│   ├── loader.py                # Façade routing by source key
│   ├── ingest_fannie.py         # Fannie Mae ingestion (origination + performance)
│   ├── ingest_fred.py           # FRED macro data ingestion
│   ├── seed_demo.py             # Demo dataset generation
│   ├── schema.py                # Validation schemas for raw data
│   └── sources.py               # Source registry definitions
├── features/                    # Feature engineering pipeline
│   ├── engineer.py              # CLI delegate for build_features()
│   ├── build_features.py        # Main feature orchestrator (reads config, runs registry)
│   ├── feature_defs.py          # Feature function registry (REGISTRY dict)
│   ├── labels.py                # Binary default labeling logic
│   └── macro_join.py            # Macro feature aggregation
├── training/                    # Model training and calibration
│   ├── trainer.py               # Main train_model() orchestrator with Prophet fallback
│   ├── train_baseline.py        # Baseline model training (logreg, RF)
│   ├── train_xgb.py             # XGBoost training helpers
│   ├── calibration.py           # Probability calibration utilities
│   ├── split.py                 # Train/test splitting strategies
│   └── interpretability.py       # Feature importance and SHAP utilities
├── models/                      # Model registry and artifacts
│   ├── registry.py              # Version control, activation, manifest JSON
│   └── artifacts/               # Joblib model files (not committed)
│       ├── {model-name}.joblib  # Latest alias
│       ├── {model-name}__YYYYMMDDTHHMMSS_*.joblib  # Versioned artifacts
│       ├── registry_manifest.json  # Model metadata and version history
│       ├── active_model.json    # Currently active model metadata
│       └── users/               # User-namespaced registries
│           └── {username}/
├── service/                     # FastAPI HTTP API and scoring
│   ├── api.py                   # Main FastAPI app with all endpoints
│   ├── model_loader.py          # ModelLoader class (load, score, explain)
│   ├── auth.py                  # JWT token and user database
│   ├── jobs.py                  # Async job queue manager
│   ├── schemas.py               # Pydantic models for requests/responses
│   └── static/                  # Static assets (UI, docs)
├── monitoring/                  # Drift detection and performance tracking
│   ├── __init__.py              # run_monitoring_job() orchestrator
│   ├── drift.py                 # Feature drift (PSI, KS test)
│   ├── score_drift.py           # Score distribution drift
│   ├── perf_drift.py            # Rolling AUC and performance tracking
│   └── metrics.py               # Statistical metric utilities
├── utils/                       # Shared utilities
│   └── logging.py               # Structured logging configuration
├── tests/                       # Test suite
│   ├── test_*.py                # Unit and integration tests
│   └── conftest.py              # Pytest fixtures
├── reports/                     # Analysis output (not committed)
│   ├── figures/                 # Visualizations
│   └── monitoring/              # Monitoring JSON and Markdown reports
├── logs/                        # Application logs (not committed)
├── scripts/                     # Utility scripts
│   └── golden_path.sh           # End-to-end test workflow
├── deploy/                      # Deployment configs
│   ├── caddy/                   # Caddy reverse proxy
│   └── nginx/                   # Nginx reverse proxy
├── .github/                     # GitHub Actions CI/CD
├── main.py                      # CLI entry point (typer app)
├── docker-compose.yml           # Local dev stack
├── docker-compose.prod.yml      # Production stack variants
├── Dockerfile                   # Container image definition
├── Makefile                     # Build targets
└── .env.prod.example            # Example production environment
```

## Directory Purposes

**config/:**
- Purpose: All application configuration
- Contains: Pydantic settings class, YAML manifests for data paths, features, training, MLflow, FRED, labeling
- Key files: `settings.py` (single source of truth for config), feature engineering groups defined in `features.yaml`

**data/:**
- Purpose: Local data storage (raw and processed)
- Contains: Ingested files (parquet, CSV), feature-engineered outputs, demo datasets
- Generated: Yes (populated by ingest commands)
- Committed: No

**data_ingestion/:**
- Purpose: Load data from external sources
- Contains: Concrete loaders per source, Fannie Mae parsing logic, FRED API client, CSV/parquet readers, demo data generation
- Key files: `loader.py` routes requests; `ingest_fannie.py` handles origination/performance parsing; `ingest_fred.py` calls FRED API

**features/:**
- Purpose: Transform raw data into engineered features
- Contains: Feature function registry, orchestrator that applies functions in dependency order, leakage guards
- Key files: `build_features.py` orchestrator; `feature_defs.py` registry of functions; `labels.py` binary default labeling; `macro_join.py` aggregates macro features

**training/:**
- Purpose: Model training with MLflow tracking
- Contains: Orchestrator supporting Prophet, sklearn classifiers, calibration logic, split strategies
- Key files: `trainer.py` main entry point; `train_baseline.py` sklearn training; `train_xgb.py` gradient boosting; `calibration.py` probability scaling

**models/:**
- Purpose: Model versioning and activation
- Contains: Local registry with manifest JSON, versioned joblib artifacts, namespace isolation
- Key files: `registry.py` implements save/load/activate/get_versions APIs; artifacts stored with SHA256 checksums

**service/:**
- Purpose: HTTP API for scoring and model management
- Contains: FastAPI application with prediction endpoints, async job queue, user auth, model catalog
- Key files: `api.py` routes (100+ endpoints); `model_loader.py` scoring and explanation; `auth.py` JWT; `jobs.py` async queue; `schemas.py` Pydantic models

**monitoring/:**
- Purpose: Drift detection and health reporting
- Contains: Feature drift (PSI), score drift, performance drift (rolling AUC) modules
- Key files: `__init__.py` orchestrator; `drift.py` feature drift; `score_drift.py` PD distribution; `perf_drift.py` rolling AUC

**utils/:**
- Purpose: Shared utilities
- Contains: Structured logging setup
- Key files: `logging.py` configures structlog with optional JSON serialization

**tests/:**
- Purpose: Unit and integration test suite
- Contains: 20+ test files covering data ingestion, features, training, service, monitoring
- Key files: `test_*.py` files follow source module structure; `conftest.py` provides fixtures

## Key File Locations

**Entry Points:**
- `main.py`: CLI entry point (typer app with commands: ingest, features, train, serve, pipeline, monitor)
- `service/api.py`: HTTP API entry point (FastAPI; 70+ endpoints)

**Configuration:**
- `config/settings.py`: Pydantic BaseSettings (single source of truth)
- `config/features.yaml`: Feature groups and definitions
- `config/training.yaml`: Model hyperparameters
- `config/data_paths.yaml`: Data directory mappings

**Core Logic:**
- `data_ingestion/loader.py`: Data source router
- `features/build_features.py`: Feature engineering orchestrator
- `training/trainer.py`: Model training orchestrator
- `models/registry.py`: Model versioning and activation
- `service/model_loader.py`: Prediction and explanation
- `monitoring/__init__.py`: Drift detection orchestrator

**Testing:**
- `tests/`: Full test suite (20+ files, pytest-based)
- `tests/conftest.py`: Pytest configuration and fixtures

## Naming Conventions

**Files:**
- `{module}_{descriptor}.py`: Specialized functionality (e.g., `train_baseline.py`, `score_drift.py`)
- `{action}.py`: Single primary action (e.g., `loader.py`, `trainer.py`, `engineer.py`)
- `{name}_defs.py`: Function/rule definitions (e.g., `feature_defs.py`)

**Directories:**
- Lowercase with underscores: `data_ingestion`, `feature_defs` (not FeatureDefs)
- Plural for collections: `features`, `models`, `tests`, `reports`, `scripts`, `logs`, `utils`
- Singular for logical concepts: `service`, `config`, `training`, `monitoring`, `data`, `deploy`

**Modules and Functions:**
- snake_case for files and functions
- CONSTANT_CASE for global constants (e.g., `_LABEL_COL`, `_FORECAST_CACHE`)
- PascalCase for classes (e.g., `ModelLoader`, `DemoTrendForecaster`)

## Where to Add New Code

**New Feature:**
- Primary code: `features/feature_defs.py` (add function to REGISTRY)
- Config: Add group/name to `config/features.yaml`
- Tests: `tests/test_features.py`

**New Model Type:**
- Implementation: `training/train_{model_type}.py`
- Orchestrator: Add case branch in `training/trainer.py`
- CLI: Add option value in `main.train()` help text
- Tests: `tests/test_training.py`

**New API Endpoint:**
- Implementation: Function in `service/api.py` decorated with `@app.get()`, `@app.post()`, etc.
- Schemas: Request/response models in `service/schemas.py`
- Auth: If user-scoped, call `_require_user()` dependency
- Tests: `tests/test_service_smoke.py`

**Utilities:**
- Shared helpers: `utils/{functionality}.py` (import as `from utils.logging import log`)
- Cross-cutting: Use existing modules in `utils/` (logging, etc.)

**Data Sources:**
- New external source: Add loader in `data_ingestion/ingest_{source}.py`
- Register in `data_ingestion/loader.py` (add case in `load()` function)
- Schema validation: Add to `data_ingestion/schema.py`

## Special Directories

**mlruns/:**
- Purpose: MLflow experiment tracking storage
- Generated: Yes (populated by MLflow during training)
- Committed: No (contains large model artifacts, experiment metadata)
- Use: View with `mlflow ui` to inspect training runs

**reports/monitoring:**
- Purpose: Monitoring job outputs (JSON + Markdown)
- Generated: Yes (by `monitoring/__init__.py` run_monitoring_job())
- Committed: No
- Contents: `drift_features.json`, `score_drift.json`, `perf_drift.json`, `summary.md`

**data/processed/fannie_mae/features/:**
- Purpose: Feature-engineered data ready for training
- Generated: Yes (by `features/build_features.py`)
- Committed: No
- Used by: Training, service prediction

**.planning/codebase/:**
- Purpose: GSD codebase analysis documents
- Generated: Yes (by codebase mapping)
- Committed: Yes
- Contents: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, STACK.md, INTEGRATIONS.md, CONCERNS.md

---

*Structure analysis: 2026-03-12*
