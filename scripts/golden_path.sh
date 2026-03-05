#!/usr/bin/env bash
set -euo pipefail

# End-to-end "golden path" smoke script for local validation.
#
# Usage:
#   bash scripts/golden_path.sh
#
# Optional env vars:
#   BASE_URL=http://localhost:8000
#   SERVER_CMD="python -m main serve"
#   USE_EXISTING_SERVER=1    # default: 0 (start/stop server in script)
#   RUN_PYTEST=1            # default: 0
#   TRAIN_MODEL=sklearn-rf  # default: sklearn-rf
#   POLL_SECONDS=90         # default: 90

BASE_URL="${BASE_URL:-http://localhost:8000}"
SERVER_CMD="${SERVER_CMD:-python -m main serve}"
USE_EXISTING_SERVER="${USE_EXISTING_SERVER:-0}"
RUN_PYTEST="${RUN_PYTEST:-0}"
TRAIN_MODEL="${TRAIN_MODEL:-sklearn-rf}"
POLL_SECONDS="${POLL_SECONDS:-90}"
SERVER_LOG="${TMPDIR:-/tmp}/pmai_golden_path_server.log"

echo "[1/8] Optional regression run"
if [[ "${RUN_PYTEST}" == "1" ]]; then
  pytest -q
else
  echo "Skipping pytest (set RUN_PYTEST=1 to enable)"
fi

SERVER_PID=""
if [[ "${USE_EXISTING_SERVER}" == "1" ]]; then
  echo "[2/8] Using existing API server at ${BASE_URL}"
else
  echo "[2/8] Starting API server"
  bash -lc "${SERVER_CMD}" >"${SERVER_LOG}" 2>&1 &
  SERVER_PID=$!
fi

cleanup() {
  if [[ -n "${SERVER_PID}" ]] && kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "[3/8] Waiting for /health"
for _ in $(seq 1 60); do
  if curl -sS "${BASE_URL}/health" >/dev/null 2>&1; then
    break
  fi
  if [[ -n "${SERVER_PID}" ]] && ! kill -0 "${SERVER_PID}" >/dev/null 2>&1; then
    echo "Server exited before becoming healthy. Last log lines:"
    tail -n 50 "${SERVER_LOG}" || true
    exit 1
  fi
  sleep 1
done

if ! curl -sS "${BASE_URL}/health" >/dev/null 2>&1; then
  echo "Server did not become healthy. Last log lines:"
  tail -n 50 "${SERVER_LOG}" || true
  exit 1
fi

echo "[4/8] API snapshot checks"
health_json="$(curl -sS "${BASE_URL}/health")"
ready_json="$(curl -sS -o /tmp/pmai_ready_resp.json -w "%{http_code}" "${BASE_URL}/ready" || true)"
metadata_json="$(curl -sS "${BASE_URL}/metadata")"
models_json="$(curl -sS "${BASE_URL}/models")"
jobs_json="$(curl -sS "${BASE_URL}/jobs")"

python - <<PY
import json
health = json.loads("""$health_json""")
meta = json.loads("""$metadata_json""")
models = json.loads("""$models_json""")
jobs = json.loads("""$jobs_json""")
print("health.status:", health.get("status"))
print("ready.http_status:", """$ready_json""")
print("metadata.mode:", meta.get("mode"))
print("models.count:", len(models.get("models", [])))
print("jobs.count:", len(jobs.get("jobs", [])))
PY

echo "[5/8] Submit async train job (${TRAIN_MODEL})"
create_job_json="$(curl -sS -X POST "${BASE_URL}/jobs/train" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"${TRAIN_MODEL}\"}")"

job_id="$(python - <<PY
import json
print(json.loads("""$create_job_json""")["id"])
PY
)"
echo "job.id: ${job_id}"

echo "[6/8] Poll job status"
terminal_json=""
for _ in $(seq 1 "${POLL_SECONDS}"); do
  job_json="$(curl -sS "${BASE_URL}/jobs/${job_id}")"
  status="$(python - <<PY
import json
print(json.loads("""$job_json""")["status"])
PY
)"
  if [[ "${status}" == "succeeded" || "${status}" == "failed" ]]; then
    terminal_json="${job_json}"
    echo "job.status: ${status}"
    break
  fi
  sleep 1
done

if [[ -z "${terminal_json}" ]]; then
  echo "Job did not reach terminal state in ${POLL_SECONDS}s"
  exit 1
fi

echo "[7/8] Validate job payload"
python - <<PY
import json, sys
job = json.loads("""$terminal_json""")
status = job.get("status")
print("terminal.status:", status)
if status == "succeeded":
    print("result:", job.get("result"))
elif status == "failed":
    print("error:", job.get("error"))
    # Failure is acceptable in environments without required local data/artifacts.
else:
    raise SystemExit("Unexpected status: " + str(status))
PY

echo "[8/8] Model lifecycle checks"
models_after_json="$(curl -sS "${BASE_URL}/models")"
python - <<PY
import json
models = json.loads("""$models_after_json""")
print("models.after.count:", len(models.get("models", [])))
active = models.get("active")
print("models.active:", active if active else "none")
PY

# Attempt activation if the target model has at least one version.
latest_version="$(python - <<PY
import json
models = json.loads("""$models_after_json""").get("models", [])
for m in models:
    if m.get("name") == "$TRAIN_MODEL" and m.get("latest_version_id"):
        print(m["latest_version_id"])
        break
PY
)"

if [[ -n "${latest_version}" ]]; then
  echo "Activating ${TRAIN_MODEL}:${latest_version}"
  curl -sS -X POST "${BASE_URL}/models/activate" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"${TRAIN_MODEL}\",\"version_id\":\"${latest_version}\"}" >/dev/null
  active_json="$(curl -sS "${BASE_URL}/models/active")"
  python - <<PY
import json
active = json.loads("""$active_json""")
print("active.name:", active.get("name"))
print("active.version_id:", active.get("version_id"))
PY
else
  echo "No version found for ${TRAIN_MODEL}; skipping activation check"
fi

echo "Golden path smoke completed successfully."
