#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_URL="${PACT_BACKEND_URL:-http://127.0.0.1:8000}"
BACKEND_PORT="${PACT_BACKEND_PORT:-8000}"
BACKEND_LOG="${PACT_BACKEND_LOG:-/tmp/pact-live-demo-backend.log}"
STARTED_BACKEND=0

healthcheck() {
  python3 - "$BACKEND_URL" <<'PY'
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
try:
    with urllib.request.urlopen(base + "/health", timeout=2) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
PY
}

start_backend() {
  echo "Starting PACT backend on ${BACKEND_URL}"
  cd "$ROOT_DIR"
  export PACT_INSECURE_DEMO_API=true
  if [ -x "$ROOT_DIR/.venv/bin/uvicorn" ]; then
    "$ROOT_DIR/.venv/bin/uvicorn" app.main:app --app-dir backend --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
  elif command -v uv >/dev/null 2>&1; then
    uv run --project backend --active uvicorn app.main:app --app-dir backend --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
  else
    python3 -m uvicorn app.main:app --app-dir backend --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
  fi
  BACKEND_PID=$!
  STARTED_BACKEND=1
}

cleanup() {
  if [ "$STARTED_BACKEND" = "1" ]; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if ! healthcheck; then
  start_backend
  for _ in $(seq 1 40); do
    if healthcheck; then
      break
    fi
    sleep 0.25
  done
fi

if ! healthcheck; then
  echo "Backend did not become healthy. See ${BACKEND_LOG}" >&2
  exit 1
fi

echo "PACT backend is healthy at ${BACKEND_URL}"
echo "Running deterministic attack/allow demos..."
python3 "$ROOT_DIR/scripts/run_demo_scenarios.py" --backend "$BACKEND_URL" --tamper
