# API Contract (Milestone 2)

This document locks the backend contract used by the frontend v1.

## Scope

v1 frontend use-cases:

1. Health and environment discovery.
2. Forecast generation (Prophet only).
3. Single and batch loan scoring.
4. Monitoring report display.
5. Async job orchestration for long-running operations.
6. Optional authenticated user-specific modeling (`/me/*`).

## Endpoints

### `GET /health`

Returns liveness and scoring model readiness.

Response:

```json
{
  "status": "ok",
  "model_loaded": true
}
```

### `GET /ready`

Deployment readiness probe.

- `200` when ready
- `503` when not ready

Response:

```json
{
  "status": "ready",
  "checks": {
    "model_loaded": true,
    "models_dir_exists": true,
    "active_model_set": true
  }
}
```

### `GET /metadata`

Frontend discovery endpoint for capabilities, mode, and artifact status.

Response fields:

- `app_name`: string
- `version`: string
- `mode`: `"demo"` or `"real-data"`
- `capabilities.ingest_sources`: list of supported ingest source keys
- `capabilities.train_models`: list of supported train model keys
- `capabilities.forecast_models`: list of forecastable model keys
- `capabilities.score_endpoints`: list of scoring endpoints
- `artifacts[]`: `{name, path, exists}`
- `monitoring_available`: `true` when `reports/monitoring/summary.md` exists

## Auth (User Mode)

### `POST /auth/register`

```json
{"username":"alice","password":"password123"}
```

### `POST /auth/login`

```json
{"username":"alice","password":"password123"}
```

Returns bearer token:

```json
{"access_token":"<token>","token_type":"bearer","username":"alice"}
```

### `GET /auth/me`

Requires `Authorization: Bearer <token>`.

### `POST /forecast`

Request:

```json
{
  "source": "fannie-mae",
  "model": "prophet",
  "horizon": 24
}
```

Notes:

- Only `model="prophet"` is accepted in v1.
- Returns HTTP `503` when Prophet artifact is missing.

Response:

```json
{
  "source": "fannie-mae",
  "model": "prophet",
  "periods": 24,
  "forecast": [
    {"ds": "2026-04-01", "yhat": 0.01, "yhat_lower": 0.008, "yhat_upper": 0.012}
  ]
}
```

### `POST /score`

Request:

```json
{
  "features": {
    "credit_score": 720,
    "orig_ltv": 80,
    "orig_dti": 35,
    "orig_upb": 350000,
    "orig_interest_rate": 6.5
  },
  "threshold": 0.5
}
```

Response:

```json
{
  "pd": 0.11,
  "decision": "current",
  "top_factors": [{"name": "orig_ltv", "value": 0.08}]
}
```

### `POST /batch_score`

Request:

```json
{
  "records": [
    {
      "features": {"credit_score": 700, "orig_ltv": 90},
      "threshold": 0.5
    }
  ]
}
```

Response:

```json
{
  "results": [
    {"pd": 0.23, "decision": "current", "top_factors": []}
  ],
  "count": 1
}
```

### `GET /monitoring/summary`

Returns the latest monitoring markdown and parsed JSON reports.

Response fields:

- `available`: bool
- `summary_markdown`: string or null
- `drift_features`: object or null
- `score_drift`: object or null
- `perf_drift`: object or null

### Jobs API (async orchestration)

Use these endpoints for long-running tasks instead of synchronous API calls.

### `POST /jobs/train`

Request:

```json
{"model": "sklearn-rf", "run_name": "rf-run-1"}
```

### `POST /jobs/pipeline`

Request:

```json
{"source": "fannie-mae", "model": "sklearn-rf"}
```

### `POST /jobs/monitor`

Request:

```json
{
  "reference_path": "data/processed/fannie_mae/features/features.parquet",
  "current_path": "data/processed/fannie_mae/features/current_period.parquet",
  "output_dir": "reports/monitoring"
}
```

All submit endpoints return HTTP `202` with a job payload:

```json
{
  "id": "job_id",
  "job_type": "train",
  "status": "queued",
  "created_at": "...",
  "started_at": null,
  "finished_at": null,
  "input_payload": {},
  "result": null,
  "error": null
}
```

### `GET /jobs/{job_id}`

Returns current job status. `status` transitions:

- `queued`
- `running`
- `succeeded`
- `failed`

### `GET /jobs?limit=50`

Returns recent jobs:

```json
{"jobs": [ ... ]}
```

## User-Scoped Endpoints (`/me/*`)

When authenticated, these endpoints isolate jobs/models per user:

- `POST /me/jobs/train`
- `GET /me/jobs`
- `GET /me/jobs/{job_id}`
- `GET /me/models`
- `GET /me/models/active`
- `GET /me/models/{name}/versions`
- `POST /me/models/activate`
- `POST /me/score`

## Model Lifecycle API

### `GET /models`

Returns model catalog and active selection:

```json
{
  "models": [
    {"name": "sklearn-rf", "version_count": 3, "latest_version_id": "20260305T171212_ab12cd34"}
  ],
  "active": {
    "name": "sklearn-rf",
    "version_id": "20260305T171212_ab12cd34",
    "artifact_path": "...",
    "current_alias_path": "...",
    "updated_at": "..."
  }
}
```

### `GET /models/{name}/versions`

Returns immutable version history with lineage metadata:

- `version_id`
- `artifact_path`
- `sha256`
- `metadata` (metrics, run id, training_data_lineage)

### `POST /models/activate`

Request:

```json
{"name": "sklearn-rf", "version_id": "20260305T171212_ab12cd34"}
```

`version_id` is optional; when omitted, latest version is activated.

### `GET /models/active`

Returns active model alias metadata. 404 if none selected yet.

## Error semantics (v1)

- `422`: payload invalid or unsupported model key for endpoint.
- `503`: required model artifact missing.
