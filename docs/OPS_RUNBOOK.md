# Ops Runbook

## Startup

```bash
python -m main serve
```

## Probes

- Liveness: `GET /health`
- Readiness: `GET /ready`

Readiness requires:

- scoring model loaded
- model artifacts directory present

## Docker Compose

API only:

```bash
docker compose up -d api
```

API + MLflow:

```bash
docker compose --profile mlflow up -d
```

## Common Incidents

### `/ready` returns 503 (`model_loaded=false`)

1. Ensure a trained model version exists (`GET /models`).
2. Activate one (`POST /models/activate`).
3. Restart API if needed.

### Train job fails: feature parquet missing

Run `pipeline` job first, then `train`.

### Pipeline fails: missing Fannie raw files

Add files under:

- `data/raw/fannie_mae/origination/Acquisition_*.txt`
- `data/raw/fannie_mae/performance/Performance_*.txt`

### Forecast fails: prophet artifact missing

Run train job with `model=prophet`.

## Verification

```bash
bash scripts/golden_path.sh
```

## CI/CD

See:

- `docs/CI_CD_RUNBOOK.md`
- `docs/TLS_HARDENING.md`
