# ── Stage 1: builder ─────────────────────────────────────────────────────────
# Installs all production deps (including compiled extensions for prophet/pystan)
# into a separate prefix so the runtime image stays slim.
FROM python:3.11-slim AS builder

WORKDIR /build

# System deps required by prophet (pystan C++ compilation)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip --no-cache-dir

# Copy package manifest and source, then install to /install prefix
COPY pyproject.toml README.md ./
COPY config/           config/
COPY data_ingestion/   data_ingestion/
COPY features/         features/
COPY training/         training/
COPY models/           models/
COPY service/          service/
COPY monitoring/       monitoring/
COPY utils/            utils/
COPY main.py           ./

RUN pip install --no-cache-dir --prefix=/install .

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Non-root user for security
RUN useradd --create-home --uid 1000 appuser

# Python packages compiled in builder
COPY --from=builder /install /usr/local

# Application source (needed alongside installed packages for config YAML, etc.)
COPY --chown=appuser:appuser . .

# Ensure mount-point directories exist and are owned by appuser
# (real data is expected to arrive via bind mounts at runtime)
RUN mkdir -p data/raw data/processed models/artifacts logs \
    && chown -R appuser:appuser /app

USER appuser

# Default env — override at runtime via -e or docker-compose environment:
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    LOG_SERIALIZE=true

EXPOSE 8000

# Healthcheck — relies on the /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "service.api:app", "--host", "0.0.0.0", "--port", "8000"]
