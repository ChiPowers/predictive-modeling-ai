# predictive-modeling-ai

This app takes in a public dataset and visualized historic and forecasted trends.

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

### Environment variables

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
