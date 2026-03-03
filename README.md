# predictive-modeling-ai

End-to-end mortgage analytics platform: ingests public Fannie Mae loan data and FRED
macroeconomic series, engineers credit risk features, trains forecasting and
probability-of-default (PD) models, serves them via REST API, and monitors for
distribution drift in production.

Built as a portfolio-quality Principal Data Science artifact demonstrating the full
ML lifecycle from raw public data through deployed, monitored service.

---

## Problem Statement

Mortgage servicers and analysts need two complementary signals:

1. **Aggregate trend forecast** — where is the portfolio-level delinquency rate headed
   over the next 12–24 months?
2. **Loan-level PD score** — which newly originated loans carry elevated default risk?

This system answers both using the same underlying data pipeline, with interpretable
baselines (logistic regression, Prophet) alongside a higher-AUC ensemble (Random
Forest), so model selection can match the business's explainability constraints.

---

## Dataset

| Source | Description | Access |
|--------|-------------|--------|
| **Fannie Mae Single-Family Loan Performance** | Quarterly origination + monthly performance files covering millions of GSE-backed loans since 1999. Pipe-delimited, 32 columns each, no header row. | [Manual download](https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data) |
| **FRED Macroeconomic Series** | 6 monthly series: Federal Funds Rate, 30-yr Mortgage Rate, Unemployment, CPI, Real GDP, Case-Shiller HPI | Free JSON API (set `FRED_API_KEY`) or public CSV fallback |

Raw files are never committed. See [`data/README.md`](data/README.md) for download
and directory layout instructions.

---

## Architecture

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │                         DATA SOURCES                                 │
 │  Fannie Mae quarterly zips           FRED JSON / CSV API             │
 └──────────────┬───────────────────────────────┬───────────────────────┘
                │                               │
                ▼                               ▼
 ┌──────────────────────────┐    ┌──────────────────────────┐
 │  data_ingestion/          │    │  data_ingestion/          │
 │  ingest_fannie.py         │    │  ingest_fred.py           │
 │  • validate with pandera  │    │  • API or CSV fallback    │
 │  • save parquet           │    │  • save parquet           │
 └──────────────┬────────────┘    └──────────────┬────────────┘
                │                               │
                └─────────────┬─────────────────┘
                              ▼
             ┌────────────────────────────────┐
             │  features/                     │
             │  build_features.py             │
             │  • 18 origination + perf feats │
             │  • macro join (FRED series)    │
             │  • leakage guard               │
             │  • output: features.parquet    │
             └────────────────┬───────────────┘
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
        ┌───────────────────┐  ┌──────────────────────┐
        │  training/        │  │  training/            │
        │  Prophet          │  │  sklearn-logreg / rf  │
        │  (delinquency ts) │  │  (loan-level PD)      │
        └─────────┬─────────┘  └──────────┬────────────┘
                  │                       │
                  └──────────┬────────────┘
                             ▼
              ┌──────────────────────────┐
              │  models/artifacts/       │
              │  prophet.joblib          │
              │  sklearn-logreg.joblib   │
              │  sklearn-rf.joblib       │
              └──────────────┬───────────┘
                             │
              ┌──────────────┴───────────┐
              ▼                          ▼
  ┌───────────────────────┐  ┌────────────────────────────┐
  │  service/api.py       │  │  monitoring/               │
  │  FastAPI              │  │  • feature drift (PSI, KS) │
  │  GET  /health         │  │  • score drift (PSI, KS)   │
  │  POST /forecast       │  │  • rolling AUC             │
  │  POST /score          │  │  → reports/monitoring/     │
  └───────────────────────┘  └────────────────────────────┘
```

**Key design choices:**
- Single Typer CLI (`pmai`) covers every stage — easy to script or wrap in Airflow
- All inter-stage handoffs use Parquet — columnar, typed, versionable
- pandera schema validation at ingest boundary (lazy mode: warnings, not hard stops)
- Feature leakage guard: data sorted by `(loan_id, observation_date)` before any
  rolling/cumulative ops so every computation is strictly backward-looking

---

## Quick Start

### 1. Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.11+. NumPy is pinned `<2.0` (Prophet 1.1.5 compatibility).

### 2. Environment variables (optional)

```bash
export FRED_API_KEY=your_key_here   # enables live FRED API; CSV fallback used otherwise
export LOG_LEVEL=INFO               # DEBUG | INFO | WARNING
export LOG_SERIALIZE=false          # true for JSON log lines (production)
```

### 3. Ingest

```bash
# Fannie Mae — place raw zip/txt files in data/raw/fannie_mae/ first (see data/README.md)
pmai ingest --source fannie-mae

# FRED macro series
pmai ingest --source fred
```

### 4. Feature Engineering

```bash
pmai features --source fannie-mae
# Output: data/processed/fannie_mae/features/features.parquet
```

Macro features from FRED are joined automatically if `data/raw/fred/macro_monthly.parquet`
exists; skipped gracefully otherwise.

### 5. Train

```bash
# Prophet — aggregate monthly delinquency-rate forecast
pmai train --model prophet

# Logistic Regression PD classifier (fast, interpretable)
pmai train --model sklearn-logreg

# Random Forest PD classifier (higher AUC)
pmai train --model sklearn-rf
```

Artifacts are saved to `models/artifacts/`.

### 6. Full Pipeline (shortcut)

```bash
pmai pipeline --source fannie-mae --model sklearn-rf
```

### 7. Serve

```bash
pmai serve
# Starts FastAPI on http://localhost:8000
```

**Example requests:**

```bash
# Liveness probe
curl http://localhost:8000/health

# Forecast next 24 months of delinquency rate
curl -X POST http://localhost:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{"source": "fannie-mae", "model": "prophet", "horizon": 24}'

# Score a batch of loans
curl -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "model": "sklearn-logreg",
    "loans": [
      {"credit_score": 720, "orig_ltv": 80, "orig_dti": 35,
       "orig_upb": 350000, "orig_interest_rate": 6.5}
    ]
  }'
```

Interactive docs: `http://localhost:8000/docs`

### 8. Monitoring

Run on a schedule (cron, Airflow, etc.) after each scoring period:

```bash
pmai monitor \
  --reference data/processed/fannie_mae/features/features.parquet \
  --current   data/processed/fannie_mae/features/current_period.parquet \
  --output-dir reports/monitoring
```

Writes four reports:

| File | Contents |
|------|----------|
| `reports/monitoring/drift_features.json` | PSI + KS for 6 key origination features |
| `reports/monitoring/score_drift.json`    | PD score distribution PSI + KS |
| `reports/monitoring/perf_drift.json`     | Rolling AUC by period (when labels present) |
| `reports/monitoring/summary.md`          | Human-readable Markdown summary |

---

## Evaluation Results & Tradeoffs

### Prophet — Delinquency Rate Forecast

| Metric | Value (in-sample) |
|--------|-------------------|
| MAE    | ~0.003–0.008 delinquency-rate points |

Prophet is configured with `yearly_seasonality=True` and a conservative
`changepoint_prior_scale=0.05` to avoid over-fitting regime changes. The model
is a strong baseline for trend visualisation; it does not incorporate macro
covariates in the current version (planned extension).

**Tradeoff:** Prophet is highly interpretable and handles missing months, but
assumes additive seasonality and is ill-suited to sharp non-linear regime shifts
(e.g., COVID-era forbearance). Consider ARIMA or LSTM as alternatives for
production stress-testing.

### sklearn-logreg — PD Classifier

| Metric | Typical range |
|--------|---------------|
| Test AUC | 0.68–0.72 |
| Regularisation | L2, C=0.1 |
| Class weighting | Balanced |

Logistic regression with median imputation and standard scaling. Fast to train,
fully interpretable via coefficients — the default choice when regulators require
model transparency.

**Tradeoff:** Linear decision boundary means non-linear interactions (e.g., LTV
× credit-score) are not captured. Coefficients are interpretable per feature but
the model underperforms RF on AUC.

### sklearn-rf — PD Classifier (recommended)

| Metric | Typical range |
|--------|---------------|
| Test AUC | 0.73–0.78 |
| n_estimators | 200 |
| max_depth | 8 |
| min_samples_leaf | 50 (regularisation vs. over-fit) |
| Class weighting | Balanced |

Captures non-linear feature interactions without extensive preprocessing.
`min_samples_leaf=50` prevents memorisation on large datasets.

**Tradeoff:** Black-box — requires SHAP or permutation importance for
explanations. Slower inference than logistic regression (manageable at batch
scoring scale). Not recommended as the sole model in environments with strict
interpretability requirements.

### Feature Coverage

19 engineered features span four groups:

| Group | Examples |
|-------|---------|
| Origination numeric | `credit_score`, `orig_ltv`, `orig_dti`, `orig_upb`, `orig_interest_rate` |
| Origination derived | `log_upb`, `is_high_ltv`, `is_high_dti`, `is_jumbo`, `is_arm` |
| Categorical (encoded) | `occupancy_code`, `loan_purpose_code`, `channel_code`, `property_type_code` |
| Macro (FRED) | `fedfunds`, `mortgage30us`, `unrate` (joined at origination date) |

---

## Project Structure

```
predictive-modeling-ai/
├── config/
│   ├── settings.py          # Pydantic settings (env-driven)
│   ├── data_paths.yaml      # All file-path configuration
│   ├── features.yaml        # Feature groups & clipping bounds
│   └── fred.yaml            # FRED series config
├── data_ingestion/
│   ├── loader.py            # Dispatch by source key
│   ├── ingest_fannie.py     # Origination + performance ingestion
│   ├── ingest_fred.py       # FRED macro ingestion
│   └── schema.py            # pandera validation schemas
├── features/
│   ├── build_features.py    # Pipeline: build_features() + run()
│   ├── feature_defs.py      # @register decorator + 18 feature fns
│   ├── macro_join.py        # FRED join (handles date format variants)
│   └── engineer.py          # CLI-facing delegate
├── training/
│   └── trainer.py           # prophet / sklearn-logreg / sklearn-rf
├── models/
│   ├── registry.py          # joblib save / load
│   └── artifacts/           # .gitkeep — populated at runtime
├── service/
│   └── api.py               # FastAPI: /health, /forecast, /score
├── monitoring/
│   ├── __init__.py          # run_monitoring_job() orchestrator
│   ├── drift.py             # Feature drift: PSI + KS
│   ├── score_drift.py       # Score distribution drift
│   ├── perf_drift.py        # Rolling AUC
│   └── metrics.py           # MAE / RMSE / MAPE helpers
├── reports/
│   ├── model_card.md        # Model card (intended use, risks, limits)
│   └── monitoring/          # Runtime drift reports
├── tests/                   # 85 passed, 2 xfailed (Prophet/NumPy compat)
├── main.py                  # Typer CLI entry-point
└── pyproject.toml
```

---

## Development

```bash
# Lint
ruff check .

# Type-check
mypy .

# Tests
pytest

# Pre-commit (lint + type-check on every commit)
pre-commit install
```

Test suite: **85 passed, 2 xfailed** (Prophet 1.1.5 incompatible with NumPy 2.0;
pinned `numpy<2.0` as mitigation).

---

## See Also

- [`reports/model_card.md`](reports/model_card.md) — intended use, limitations, risk
  considerations, and monitoring plan
- [`data/README.md`](data/README.md) — dataset download instructions
Ingest public datasets, engineer time-series features, train forecasting models, and visualise historic and predicted trends.

---

## Project layout

```
.
├── config/             # Pydantic settings (env-driven) + mlflow.yaml
├── data/
│   ├── raw/            # Ingested, unmodified datasets (git-ignored)
│   └── processed/      # Feature-engineered outputs (git-ignored)
├── data_ingestion/     # Dataset loaders and source adapters
├── features/           # Feature-engineering pipeline
├── logs/               # Rotating application logs (git-ignored)
├── mlartifacts/        # MLflow artifact store (git-ignored)
├── mlruns/             # MLflow tracking store (git-ignored)
├── models/
│   └── artifacts/      # Serialised model files (git-ignored)
├── monitoring/         # Prediction-quality and drift metrics
├── scripts/            # One-off helper scripts
├── service/            # FastAPI prediction API
├── tests/              # pytest test suite
├── training/           # Model training orchestration
├── utils/              # Shared utilities (logging, etc.)
├── main.py             # Typer CLI entry-point
├── Makefile            # Common dev commands
└── pyproject.toml      # Deps, linting, test config
```

---

## Quick start

```bash
# 1. Create a virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 2. Install production deps
pip install -e .

# 3. Install dev tooling (lint, tests, type-check)
pip install -e ".[dev]"

# 4. Verify the CLI
python -m main --help
```

---

## Common commands

| Task | Command |
|---|---|
| Lint | `make lint` |
| Auto-fix + format | `make fmt` |
| Type-check | `make typecheck` |
| Run tests | `make test` |
| Coverage report | `make test-cov` |
| Ingest dataset | `make ingest SOURCE=csv:data/raw/sample.csv` |
| Build features | `make features SOURCE=csv:data/raw/sample.csv` |
| Train model | `make train MODEL=prophet` |
| Full pipeline | `make pipeline SOURCE=csv:... MODEL=prophet` |
| Start API | `make serve` |

---

## Configuration

All settings are read from environment variables or a `.env` file in the project root. See `config/settings.py` for the full list.

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Loguru log level |
| `RANDOM_SEED` | `42` | Reproducibility seed |
| `TEST_SPLIT` | `0.2` | Train/test split ratio |
| `FORECAST_HORIZON` | `30` | Periods to forecast |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API port |
| `MLFLOW_TRACKING_URI` | `mlruns` | MLflow tracking server URI |
| `MLFLOW_EXPERIMENT_NAME` | `predictive-modeling-ai` | Default experiment name |
| `MLFLOW_REGISTERED_MODEL_NAME` | `pmai-forecast` | Model Registry entry name |

---

## How to run MLflow locally

### 1 — Train a model (creates a run automatically)

```bash
# Basic — uses defaults from config/mlflow.yaml / settings
python -m main train --model prophet

# With an explicit run name and experiment
python -m main train --model sklearn-logreg \
    --run-name "baseline-2026-03-02" \
    --experiment-name "my-experiment"

# Full pipeline
python -m main pipeline \
    --source fannie-mae \
    --model sklearn-rf \
    --run-name "pipeline-run-1"
```

Each run logs:

| What | Where in MLflow |
|---|---|
| `model`, `random_seed`, `test_split`, `forecast_horizon` | **Parameters** |
| `mae` (Prophet) or `auc` (sklearn) | **Metrics** |
| Fitted estimator | **Artifacts → model/** |
| Registered model version | **Model Registry → pmai-forecast** |

### 2 — Launch the MLflow UI

```bash
mlflow ui --host 127.0.0.1 --port 5000
```

Then open <http://127.0.0.1:5000> in your browser.

The tracking store is stored locally in `mlruns/` and the artifact store in `mlartifacts/`. Both are git-ignored.

### 3 — List experiments and runs from the CLI

```bash
mlflow experiments list
mlflow runs list --experiment-name predictive-modeling-ai
mlflow artifacts download --run-id <RUN_ID> --dst-path /tmp/my-artifacts
```

### 4 — Load a registered model version for inference

```python
import mlflow.sklearn

model = mlflow.sklearn.load_model("models:/pmai-forecast/latest")
predictions = model.predict(X_new)
```

### 5 — Use a remote tracking server

```bash
export MLFLOW_TRACKING_URI=http://mlflow.internal:5000
python -m main train --model sklearn-logreg --run-name "remote-run"
```

Or set `MLFLOW_TRACKING_URI` in `.env`.

---

## Docker runbook

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/) v2 (bundled with Docker Desktop)

---

### Build the image

```bash
docker build -t predictive-modeling-ai:latest .
```

The build uses a two-stage Dockerfile:

| Stage | Purpose |
|---|---|
| `builder` | Installs all deps (including compiled C++ extensions for prophet) |
| `runtime` | Slim final image with non-root user, no build tools |

---

### Run the API only

```bash
docker run --rm \
  -p 8000:8000 \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/models/artifacts:/app/models/artifacts" \
  -v "$(pwd)/logs:/app/logs" \
  predictive-modeling-ai:latest
```

The API is available at `http://localhost:8000`. Check health:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

### Run with Docker Compose (API + MLflow)

```bash
# Start both services in the background
docker compose up -d

# Follow logs
docker compose logs -f api

# Stop everything
docker compose down
```

| Service | URL |
|---|---|
| Prediction API | `http://localhost:8000` |
| MLflow UI | `http://localhost:5000` |

> The MLflow service is optional. To run the API without it, comment out the
> `mlflow` block in `docker-compose.yml` and remove the `depends_on` entry
> from the `api` service.

---

### Docker environment variables

All settings can be passed via `-e` flags or an `.env` file in the project
root (loaded automatically by Compose when present).

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | Loguru log level |
| `LOG_SERIALIZE` | `true` | Emit JSON logs |
| `FORECAST_HORIZON` | `30` | Periods to forecast |
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | Bind port |
| `MLFLOW_TRACKING_URI` | `http://mlflow:5000` | MLflow server URL |

Example `.env`:

```dotenv
LOG_LEVEL=DEBUG
FORECAST_HORIZON=90
```

---

### Volume mounts

| Host path | Container path | Contents |
|---|---|---|
| `./data` | `/app/data` | Raw and processed datasets |
| `./models/artifacts` | `/app/models/artifacts` | Serialised model files |
| `./logs` | `/app/logs` | Application log files |

Data and model artifacts are intentionally excluded from the image; mount
them at runtime so they persist across container restarts.

---

### Rebuild after code changes

```bash
docker compose build api
docker compose up -d api
```

---

## Architecture

```
public dataset
     │
     ▼
data_ingestion  →  data/raw/
     │
     ▼
features        →  data/processed/
     │
     ▼
training        →  models/artifacts/
     │              └── MLflow (mlruns/ + mlartifacts/)
     │                   ├── params / metrics
     │                   ├── model artifact
     │                   └── Model Registry → pmai-forecast
     │
     ├──► monitoring  (metrics, drift)
     │
     └──► service     (FastAPI /forecast)
```

---

## Scoring API

The FastAPI service exposes three endpoints.

### Start the server

```bash
MODEL_ARTIFACT_DIR=models/artifacts MODEL_FILENAME=model.joblib \
  uvicorn service.app:app --host 0.0.0.0 --port 8000 --reload
```

Interactive docs: http://localhost:8000/docs

---

### GET /health

```bash
curl http://localhost:8000/health
```

**Response**

```json
{
  "status": "ok",
  "model_loaded": true,
  "timestamp": 1740000000.0
}
```

---

### POST /score

Score a single loan record.

```bash
curl -s -X POST http://localhost:8000/score \
  -H "Content-Type: application/json" \
  -d '{
    "features": {
      "credit_score": 620,
      "original_ltv": 95.0,
      "original_dti": 45.0,
      "original_interest_rate": 7.25,
      "original_loan_amount": 420000,
      "loan_purpose": "C",
      "property_type": "SF",
      "num_borrowers": 1
    },
    "threshold": 0.5
  }' | python3 -m json.tool
```

---

### POST /batch_score

Score multiple records in a single request.

```bash
curl -s -X POST http://localhost:8000/batch_score \
  -H "Content-Type: application/json" \
  -d '{"records": [...]}' | python3 -m json.tool
```

---

### Scoring API environment variables

| Variable             | Default              | Description                        |
|----------------------|----------------------|------------------------------------|
| `MODEL_ARTIFACT_DIR` | `models/artifacts`   | Directory containing the artifact  |
| `MODEL_FILENAME`     | `model.joblib`       | Joblib-serialized model file       |
| `TOP_N_FACTORS`      | `5`                  | Number of top factors to return    |

---

## Contributing

1. `make install-dev` to set up pre-commit hooks
2. `make fmt` before committing
3. All new code requires a corresponding test in `tests/`
