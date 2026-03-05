# predictive-modeling-ai

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
