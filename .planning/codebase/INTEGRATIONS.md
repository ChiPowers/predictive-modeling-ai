# External Integrations

**Analysis Date:** 2026-03-12

## APIs & External Services

**FRED (Federal Reserve Economic Data):**
- Service: St. Louis Federal Reserve macroeconomic data API
- What it's used for: Download economic indicators (fed funds rate, mortgage rates, unemployment) for feature engineering
- SDK/Client: httpx (async HTTP client)
- Auth: Optional API key via `FRED_API_KEY` env var
- Endpoints:
  - Authenticated: `https://api.stlouisfed.org/fred/series/observations` (JSON)
  - Public fallback: `https://fred.stlouisfed.org/graph/fredgraph.csv` (CSV)
- Config file: `config/fred.yaml` - Defines series IDs, resampling methods, observation start date
- Usage: `data_ingestion.ingest_fred.ingest_fred()` - Called via CLI `pmai ingest --source fred`
- Timeout: 30 seconds (configurable in fred.yaml)

**Fannie Mae Single-Family Loan Performance Data:**
- Service: Public mortgage loan dataset (local file ingest, not remote API)
- What it's used for: Historical origination and performance data for default prediction
- Format: Fixed-width text files (Acquisition_*.txt, Performance_*.txt)
- Config: `config/fannie_mae.yaml` (schema and file paths)
- Usage: `data_ingestion.ingest_fannie.py` - Parses and validates raw Fannie Mae files
- Storage: `data/raw/fannie_mae/{origination,performance}/`

## Data Storage

**Databases:**
- SQLite (local auth only) - `data/auth/users.sqlite3`
  - Client: sqlite3 (stdlib)
  - Purpose: User credentials for auth-enabled deployments
  - Schema: Single `users` table with username, password_hash, created_at
  - Connection: Local file-based, no remote connection

**File Storage:**
- Local filesystem only (no S3/cloud integration)
- Directories:
  - Raw data: `data/raw/{fred,fannie_mae}/*.{parquet,txt}`
  - Processed features: `data/processed/*.parquet`
  - Model artifacts: `models/artifacts/{prophet,sklearn-logreg,sklearn-rf}.joblib`
  - Logs: `logs/app.log`
  - MLflow artifacts: `mlruns/` (local backend by default)

**Caching:**
- In-process dictionary cache for loaded forecast models in `service/api.py` (variable `_FORECAST_CACHE`)
- No external cache service (Redis, Memcached)

## Authentication & Identity

**Auth Provider:**
- Custom local implementation (no third-party OAuth/OIDC)
  - Implementation: `service/auth.py`
  - User storage: SQLite (`data/auth/users.sqlite3`)
  - Password hashing: PBKDF2-HMAC-SHA256 with random salt (200,000 iterations)
  - Token format: Custom JWT-like (base64url payload + HMAC-SHA256 signature, no standard library)
  - Token TTL: 720 minutes (12 hours) via `AUTH_TOKEN_TTL_MINUTES` env var
  - Secret: `AUTH_SECRET` env var (default: "change-me-dev-secret" - must change in production)

**Endpoints:**
- POST `/auth/register` - Create new user account
- POST `/auth/login` - Authenticate and receive bearer token
- GET `/auth/me` - Verify current user (requires bearer token)

**Scoped Features:**
- User namespace support for multi-tenant model training/storage via `namespace` parameter
- User-scoped jobs: `/me/jobs/*` endpoints
- User-scoped models: `/me/models/*` endpoints

## Monitoring & Observability

**Error Tracking:**
- None detected (errors logged only)

**Logs:**
- stdout/stderr via Uvicorn (FastAPI) and loguru
- File-based: `logs/app.log` (if running as service)
- Structured logging: JSON format when `LOG_SERIALIZE=true` (enabled in docker-compose.yml)
- Log level: `LOG_LEVEL` env var (default: INFO)

**Monitoring Job Output:**
- Reports written to `reports/monitoring/`:
  - `drift_features.json` - Feature distribution drift
  - `score_drift.json` - Model prediction drift
  - `perf_drift.json` - Performance metrics (rolling AUC)
  - `summary.md` - Human-readable markdown summary
- Endpoint: GET `/monitoring/summary` - Returns latest reports for frontend

## CI/CD & Deployment

**Hosting:**
- Render.com (primary, via render.yaml)
- Docker Compose (local development)
- Self-hosted Docker deployments supported

**CI Pipeline:**
- None detected (render.yaml has `autoDeploy: true` from git push)

**Deployment Configuration:**
- `render.yaml` - Render.com service definition
  - Web service: pmai-web
  - Docker build from `./Dockerfile`
  - Health check: `/health` endpoint
  - Region: oregon (configurable)
  - Low memory mode: enabled (1500 max training rows)

- `docker-compose.yml` - Local development
  - API service on port 8000
  - Optional MLflow tracking server on port 5000 (profile: mlflow)
  - Volumes: ./data, ./models/artifacts, ./logs

- `docker-compose.prod.yml` - Production (basic)
- `docker-compose.prod.tls.yml` - Production with TLS
- `docker-compose.prod.caddy.yml` - Production with Caddy reverse proxy

**Container Images:**
- Runtime: `python:3.11-slim` (builder stage uses full 3.11 for compilation)
- MLflow server: `ghcr.io/mlflow/mlflow:v2.13.2` (optional, profile-based)

## Environment Configuration

**Required env vars:**
- `FRED_API_KEY` - FRED API authentication (optional; falls back to public CSV endpoint)
- `MLFLOW_TRACKING_URI` - MLflow server URI (default: `mlruns` for local file backend)

**Important env vars:**
- `LOG_LEVEL` - Logging verbosity (default: INFO)
- `LOG_SERIALIZE` - JSON structured logging (default: false)
- `API_HOST` - Bind address (default: 0.0.0.0)
- `API_PORT` - Listen port (default: 8000, overridden by `PORT` env var in Render)
- `FORECAST_HORIZON` - Default forecast periods (default: 30)
- `LOW_MEMORY_MODE` - Reduce training data for constrained environments (default: false)
- `AUTH_ENABLED` - Enable/disable authentication (default: true)
- `AUTH_SECRET` - JWT signing secret (MUST change in production)
- `AUTH_TOKEN_TTL_MINUTES` - Token expiration (default: 720 = 12 hours)

**Secrets location:**
- Environment variables (via `.env` file or container env)
- `.env` file NOT committed (listed in .gitignore)
- Example template: `.env.prod.example`

## Webhooks & Callbacks

**Incoming:**
- None detected (API is REST-only, no webhook endpoints)

**Outgoing:**
- None detected (no external service callbacks)

**Background Jobs:**
- In-process ThreadPoolExecutor (2 workers max) via `service/jobs.py`
- No message queue (Celery, RabbitMQ) or external job service
- Job types: train, pipeline, monitor, seed-demo
- Job state: In-memory only (lost on service restart)

## Data Sources

**Ingestion Sources:**
- `fred` - FRED API economic data
- `fannie-mae` - Local Fannie Mae mortgage files
- `csv:<path>` - Load CSV from local filesystem
- `parquet:<path>` - Load Parquet from local filesystem

**Forecast Models:**
- Only Prophet (`prophet`) supports forecast endpoint
- Scoring models: prophet, sklearn-logreg, sklearn-rf

---

*Integration audit: 2026-03-12*
