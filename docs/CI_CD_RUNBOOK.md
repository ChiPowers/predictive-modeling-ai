# CI/CD Runbook

## Overview

This repository uses two GitHub Actions workflows:

- `.github/workflows/ci.yml`
- `.github/workflows/deploy.yml`

## CI Workflow

Triggers:

- Push to `main` and `emdash/**`
- Pull requests to `main`

Stages:

1. `quality`
   - `ruff check .`
   - `mypy .`
2. `test`
   - `pytest -v --cov=. --cov-report=term-missing`
3. `docker-build`
   - Builds Docker runtime image (`target=runtime`) without push

## Deploy Workflow

Trigger:

- Manual (`workflow_dispatch`)

Inputs:

- `environment`: `staging` or `production`
- `image_tag`: tag for GHCR image
- `dry_run`: `true|false`

Behavior:

- Validates Docker Compose config.
- Builds runtime image.
- Pushes to `ghcr.io/<owner>/<repo>:<image_tag>` when `dry_run=false`.
- Uses GitHub Environment for approval gates.

## Promotion Gate Setup

Set in GitHub repository settings:

1. Environments:
   - `staging`
   - `production`
2. Add protection rules:
   - required reviewers for `production`
   - optional wait timer/change windows

This enforces explicit approval before production deploy jobs run.

## Standard Promotion Flow

1. Merge to `main` and wait for CI green.
2. Run Deploy workflow:
   - `environment=staging`
   - `image_tag=sha-<commit>`
   - `dry_run=false`
3. Validate staging.
4. Re-run Deploy workflow:
   - `environment=production`
   - same `image_tag`
   - `dry_run=false`

Deployment target/runtime details:

- `docker-compose.prod.yml`
- `docs/DEPLOYMENT_PROD.md`

## Failure Triage

### CI `quality` fails

- Run locally:
  - `ruff check .`
  - `mypy .`

### CI `test` fails

- Run locally:
  - `pytest -q`

### CI `docker-build` fails

- Run locally:
  - `docker build --target runtime -t predictive-modeling-ai:local .`

### Deploy push fails

- Confirm `dry_run=false`.
- Confirm repository package permissions for GHCR.
- Confirm `packages: write` permission in workflow and repo policies.
