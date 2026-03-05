# Production Deployment Guide

This guide deploys PMAI as a web service behind Nginx using Docker Compose.

## Files

- `docker-compose.prod.yml`
- `deploy/nginx/nginx.conf`
- `.env.prod.example`

## 1. Prepare host

Install:

- Docker Engine 24+
- Docker Compose v2

Open firewall ports:

- `80/tcp` (or `443` if TLS is terminated elsewhere)

## 2. Configure environment

```bash
cp .env.prod.example .env.prod
```

Edit `.env.prod`:

- `IMAGE_TAG` (from CI/CD deploy workflow)
- `PUBLIC_PORT`
- optional `MLFLOW_TRACKING_URI`

## 3. Pull and start

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

## 4. Verify service

```bash
curl http://<host>/health
curl -i http://<host>/ready
```

Open:

- `http://<host>/` (UI)

## 5. First model activation

If `/ready` returns 503 because no active model is loaded:

1. Run pipeline/train jobs from UI.
2. Activate model in **Model Lifecycle** panel.
3. Re-check `/ready`.

## 6. Upgrade flow

1. Run deploy workflow in GitHub Actions with new `IMAGE_TAG`.
2. On host:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod pull
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

3. Validate `/ready` and UI.

## 7. Rollback

1. Set previous known-good `IMAGE_TAG` in `.env.prod`.
2. Re-run:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

## Notes

- This setup uses HTTP at Nginx level by default.
- For TLS, terminate at an external load balancer/reverse proxy, or extend Nginx config with certificates.

For built-in TLS deployment options, see:

- `docs/TLS_HARDENING.md`
