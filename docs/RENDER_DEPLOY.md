# Deploying on Render with `render.yaml`

This repo now includes a root `render.yaml` Blueprint for Render.

## Why `render.yaml` can be ignored

Render only applies `render.yaml` when you create or sync a **Blueprint**.

If you created a Web Service manually first, Render does not automatically switch that
service to Blueprint-managed config from your repo file.

## Deploy using Blueprint (recommended)

1. Push this repo (with `render.yaml`) to GitHub.
2. In Render: **New +** -> **Blueprint**.
3. Select your repo/branch.
4. Confirm the service plan/region/name and create.
5. Wait for build/deploy, then open:
   - `/health`
   - `/ready`

## Lowest-cost profile (portfolio/demo)

The current `render.yaml` is configured for lowest cost:

- no persistent disk
- `AUTH_ENABLED=false` (demo mode)
- Docker deploy + `/health` check

Tradeoff: data, trained models, and user state are ephemeral and may reset on
restart/redeploy.

## Existing service already on Render

If your current service was created manually, do one of these:

- Create a new service via **Blueprint** (cleanest).
- Or move to Blueprint management in Render, then run a Blueprint sync.

If neither is done, changing `render.yaml` in GitHub will not change the running service.

## What this Blueprint configures

- Docker deploy using `Dockerfile`
- Dynamic Render port via container startup command already in Dockerfile
- Health check path: `/health`
- Demo-first auth setting (`AUTH_ENABLED=false`)

## Demo vs user-login modes

You can run two Render services from this same codebase:

1. Demo mode service:
   - `AUTH_ENABLED=false`
2. User mode service:
   - `AUTH_ENABLED=true`
   - set `AUTH_SECRET=<generated-secret>`
   - add persistent disk if you want user/model state to survive restarts

Simplest setup: duplicate the service in Render and change only those env vars.
