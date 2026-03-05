# TLS Hardening Guide

## What is TLS?

TLS is the encryption behind `https://`.

Without TLS:

- traffic can be intercepted/modified
- login/session data can be exposed
- browsers mark your site as "Not Secure"

With TLS:

- browser-to-server traffic is encrypted
- users see trusted HTTPS lock icon
- safer for public web access

## Which option should you choose?

### Option A (easier): Caddy auto TLS

Use when:

- you have a real public domain name
- server is reachable on ports `80` and `443`
- you want automatic certificate issuance/renewal

Files:

- `docker-compose.prod.caddy.yml`
- `deploy/caddy/Caddyfile`
- `.env.prod.tls.example`

Run:

```bash
cp .env.prod.tls.example .env.prod
# set DOMAIN and ACME_EMAIL in .env.prod
docker compose -f docker-compose.prod.caddy.yml --env-file .env.prod up -d
```

### Option B (more control): Nginx + your cert files

Use when:

- you already manage certs (corporate PKI, certbot, cloud-issued certs)
- you want explicit Nginx policy control (rate limiting, headers, TLS settings)

Files:

- `docker-compose.prod.tls.yml`
- `deploy/nginx/nginx.tls.conf`
- `.env.prod.tls.example`

Requirements:

`TLS_CERTS_DIR` must contain:

- `fullchain.pem`
- `privkey.pem`

Run:

```bash
cp .env.prod.tls.example .env.prod
# set TLS_CERTS_DIR and IMAGE_TAG in .env.prod
docker compose -f docker-compose.prod.tls.yml --env-file .env.prod up -d
```

## Security controls included

- HTTPS-only (HTTP -> HTTPS redirect in Nginx TLS config)
- HSTS header
- X-Content-Type-Options, X-Frame-Options, Referrer-Policy
- Basic request rate limit (Nginx TLS option)

## Post-deploy checks

```bash
curl -I https://<your-domain>/health
curl -i https://<your-domain>/ready
```

Expected:

- `/health` -> `200`
- `/ready` -> `200` after model activation

## Important notes

- For local dev without a domain, stick with HTTP compose.
- Auto TLS (Caddy) needs public DNS + open `80/443`.
- If behind a cloud load balancer that already terminates TLS, you can keep app-side HTTP and enforce TLS at the LB.
