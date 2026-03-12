# Technology Stack

**Analysis Date:** 2026-03-12

## Languages

**Primary:**
- Python 3.11 - All backend code (training, inference, API, data ingestion)

**Secondary:**
- HTML/CSS/JavaScript - Frontend UI (mounted in `service/static/`)

## Runtime

**Environment:**
- Python 3.11-slim (Docker: `python:3.11-slim`)
- Unix-based (development on macOS, Docker containers)

**Package Manager:**
- pip (via setuptools)
- Lockfile: pyproject.toml (PEP 517/518 compliant)

## Frameworks

**Core:**
- FastAPI 0.111.1 - REST API server for predictions and model management
- Uvicorn 0.30.1 (standard extras) - ASGI server for FastAPI
- Typer 0.12.3 - CLI framework for ingest/train/pipeline/monitor commands

**ML/Forecasting:**
- Prophet 1.1.5 - Time series forecasting (primary model)
- scikit-learn >=1.5,<2.0 - Logistic regression and random forest classifiers
- xgboost >=2.0,<3.0 - Boosted tree models
- statsmodels 0.14.2 - Statistical methods and ARIMA support
- scipy 1.13.1 - Numerical computing and optimization

**Interpretability:**
- SHAP >=0.45,<1.0 - Feature importance and model explanations
- Matplotlib >=3.9,<4.0 - Static plotting for SHAP

**Data Processing:**
- pandas 2.2.3 - DataFrames and time series manipulation
- numpy >=1.26.4,<2.0 - Numerical arrays (constrained for Prophet compatibility)
- PyArrow 16.1.0 - Parquet I/O and data serialization
- pandera 0.20.3 - DataFrame schema validation

**Visualization:**
- Plotly 5.22.0 - Interactive charts and frontend visualizations
- Kaleido 0.2.1 - Static image export for Plotly

**Configuration/Validation:**
- Pydantic 2.7.4 - Data validation and API schemas
- pydantic-settings 2.3.4 - Environment-based configuration
- PyYAML 6.0.2 - YAML config file parsing

**Experiment Tracking:**
- MLflow >=2.17 - Model registry and training experiment tracking
- joblib 1.4.2 - Model serialization (pickle alternative)

**Logging:**
- loguru 0.7.2 - Structured logging with file/console/JSON support

**HTTP Client:**
- httpx 0.27.0 - Async HTTP client for external API calls (FRED)

## Testing

**Framework:**
- pytest 8.2.2 - Test runner
- pytest-cov 6.0.0 - Coverage reporting

**Code Quality:**
- ruff 0.4.10 - Fast linter and formatter (replaces black + isort + flake8)
- mypy 1.10.1 - Static type checking
- pre-commit 3.7.1 - Git hook automation

**Type Stubs:**
- types-requests 2.32.0.20240712 - Type hints for requests library

## Key Dependencies

**Critical:**
- Prophet 1.1.5 - Core forecasting model; requires C++ compilation (pystan) in builder stage
- scikit-learn - Dependency for logistic regression and random forest scoring models
- pandas 2.2.3 - All data processing pipelines

**Infrastructure:**
- FastAPI + Uvicorn - Production API with automatic OpenAPI documentation
- MLflow >=2.17 - Artifact storage and experiment tracking for reproducibility

## Configuration

**Environment:**
- `.env` file optional (via pydantic-settings)
- Docker environment variables override .env
- Key env vars: `FRED_API_KEY`, `MLFLOW_TRACKING_URI`, `LOG_LEVEL`, `API_HOST`, `API_PORT`, `AUTH_ENABLED`

**Build:**
- `pyproject.toml` - Single source of truth for dependencies and tool config
- `Dockerfile` - Two-stage build (builder for compiled deps, runtime for slim image)
- `docker-compose.yml` - Local dev with optional MLflow tracking server (profile: mlflow)
- `docker-compose.prod.yml`, `.prod.caddy.yml`, `.prod.tls.yml` - Production variants
- `render.yaml` - Render.com deployment config (web service definition)

**Application Config:**
- `config/settings.py` - Pydantic settings class loaded from environment
- `config/fred.yaml` - FRED API series and endpoint configuration

## Platform Requirements

**Development:**
- Python 3.11+
- Docker (for containerized builds)
- System build tools for prophet/pystan C++ compilation (gcc, g++)

**Production:**
- Docker runtime or Python 3.11 interpreter
- Optional: MLflow tracking server (ghcr.io/mlflow/mlflow:v2.13.2)
- Minimum 512MB RAM (low_memory_mode available for constrained environments)
- Network access to FRED API (https://api.stlouisfed.org/fred/)

**Deployment:**
- Render.com (via render.yaml) OR
- Docker Compose (local/self-hosted)
- Health checks expect `/health` and `/ready` endpoints on configured API_PORT

---

*Stack analysis: 2026-03-12*
