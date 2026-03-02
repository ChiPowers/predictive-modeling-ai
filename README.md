# predictive-modeling-ai

Ingest public datasets, engineer time-series features, train forecasting models, and visualise historic and predicted trends.

---

## Project layout

```
.
├── config/             # Pydantic settings (env-driven)
├── data/
│   ├── raw/            # Ingested, unmodified datasets (git-ignored)
│   └── processed/      # Feature-engineered outputs (git-ignored)
├── data_ingestion/     # Dataset loaders and source adapters
├── features/           # Feature-engineering pipeline
├── logs/               # Rotating application logs (git-ignored)
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
     │
     ├──► monitoring  (metrics, drift)
     │
     └──► service     (FastAPI /forecast)
```

---

## Contributing

1. `make install-dev` to set up pre-commit hooks
2. `make fmt` before committing
3. All new code requires a corresponding test in `tests/`
