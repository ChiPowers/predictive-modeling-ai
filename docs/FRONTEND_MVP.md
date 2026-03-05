# Frontend MVP (Milestone 3)

The frontend is a static web UI served by FastAPI.

## Run

```bash
python -m main serve
```

Open:

- `http://localhost:8000/` for the UI
- `http://localhost:8000/docs` for OpenAPI docs

## Features

- Login/register panel for optional private user mode (`/auth/*`)
- Snapshot cards for:
  - `/health`
  - `/metadata`
  - `/monitoring/summary`
- Forecast form wired to `/forecast`
- Single score form wired to `/score`
- Batch score form wired to `/batch_score`
- Async jobs panel wired to:
  - `/jobs/train`
  - `/jobs/pipeline`
  - `/jobs/monitor`
  - `/jobs` polling
- In logged-in mode, jobs/models calls are automatically routed to `/me/*`

## Files

- `service/static/index.html`
- `service/static/styles.css`
- `service/static/app.js`

## Operator Guide

- `docs/UI_OPERATOR_RUNBOOK.md`
- `docs/ONBOARDING_CHECKLIST.md`
- `docs/OPS_RUNBOOK.md`
