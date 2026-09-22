#!/bin/bash

set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOCAL_API="http://127.0.0.1:8000"
LOCAL_WEB="http://127.0.0.1:3000"
PUBLIC_API="https://api.fwor1d.ru"
PUBLIC_WEB="https://beanfeature.fwor1d.ru"
LOG_DIR="/tmp/beanfeature-presentation-named"
mkdir -p "$LOG_DIR"

API_PID=""
WORKER_PID=""
WEB_PID=""

cleanup() {
    trap - INT TERM EXIT
    echo
    echo "Stopping BeanFeature Lab application processes..."
    for pid in "$WEB_PID" "$WORKER_PID" "$API_PID"; do
        if [ -n "$pid" ]; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    for _ in {1..5}; do
        remaining=0
        for pid in "$WEB_PID" "$WORKER_PID" "$API_PID"; do
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                remaining=1
            fi
        done
        [ "$remaining" -eq 0 ] && break
        sleep 1
    done
    for pid in "$WEB_PID" "$WORKER_PID" "$API_PID"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done
    for pid in "$WEB_PID" "$WORKER_PID" "$API_PID"; do
        if [ -n "$pid" ]; then
            wait "$pid" 2>/dev/null || true
        fi
    done
    echo "Cloudflare system tunnel was not touched."
}
trap cleanup INT TERM EXIT

if [ ! -x .venv/bin/alembic ] || [ ! -x .venv/bin/uvicorn ] || [ ! -x .venv/bin/beanfeature-worker ]; then
    echo "ERROR: Project .venv is missing or incomplete. Run 'make setup'." >&2
    exit 1
fi
for binary in node npm curl lsof shasum; do
    if ! command -v "$binary" >/dev/null 2>&1; then
        echo "ERROR: Required command '$binary' is unavailable." >&2
        exit 1
    fi
done
if [ ! -f apps/web/node_modules/next/dist/bin/next ]; then
    echo "ERROR: Next.js dependencies are missing. Run 'npm install' in apps/web." >&2
    exit 1
fi

if ! command -v cloudflared >/dev/null 2>&1; then
    echo "WARNING: cloudflared is not installed; local app can start, public hosting cannot."
fi
if command -v pgrep >/dev/null 2>&1 && pgrep -f 'cloudflared tunnel run' >/dev/null 2>&1; then
    SYSTEM_TUNNEL_PROCESS=1
else
    SYSTEM_TUNNEL_PROCESS=0
    echo "WARNING: Named cloudflared service process not found; local app will still start."
fi

for port in 8000 3000; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN -t | grep -q .; then
        echo "ERROR: Local port $port is occupied. Stop that process before presentation." >&2
        exit 1
    fi
done

build_fingerprint() {
    {
        printf 'browser_api=%s\nread_only=1\n' "$PUBLIC_API"
        shasum -a 256 apps/web/package.json apps/web/package-lock.json apps/web/next.config.ts apps/web/tsconfig.json
        find apps/web/src -type f -not -name '.DS_Store' -exec shasum -a 256 {} +
    } | LC_ALL=C sort | shasum -a 256 | awk '{print $1}'
}

FINGERPRINT="$(build_fingerprint)"
SAVED_FINGERPRINT=""
if [ -f apps/web/.next/beanfeature-named-build.sha256 ]; then
    SAVED_FINGERPRINT="$(<apps/web/.next/beanfeature-named-build.sha256)"
fi

echo "Applying database migrations..."
.venv/bin/alembic upgrade head

if [ -f apps/web/.next/BUILD_ID ] && [ "$SAVED_FINGERPRINT" = "$FINGERPRINT" ]; then
    echo "Using current production frontend build."
else
    echo "Building production frontend for $PUBLIC_API..."
    if ! (cd apps/web && \
        NEXT_PUBLIC_API_BASE_URL="$PUBLIC_API" \
        NEXT_PUBLIC_DEMO_READ_ONLY=1 \
        BEANFEATURE_INTERNAL_API_BASE_URL="$LOCAL_API" \
        npm run build > "$LOG_DIR/build.log" 2>&1); then
        echo "ERROR: Frontend build failed. See $LOG_DIR/build.log" >&2
        tail -30 "$LOG_DIR/build.log" >&2
        exit 1
    fi
    printf '%s\n' "$FINGERPRINT" > apps/web/.next/beanfeature-named-build.sha256
fi

wait_for_local() {
    local url="$1"
    local label="$2"
    local pid="$3"
    for _ in {1..30}; do
        if curl --silent --fail --max-time 2 "$url" -o /dev/null 2>/dev/null; then
            echo "$label: OK"
            return 0
        fi
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "ERROR: $label process exited. See logs in $LOG_DIR." >&2
            return 1
        fi
        sleep 1
    done
    echo "ERROR: $label health check timed out. See logs in $LOG_DIR." >&2
    return 1
}

echo "Starting FastAPI..."
BEANFEATURE_CORS_ORIGINS="$PUBLIC_WEB,http://127.0.0.1:3000,http://localhost:3000" \
BEANFEATURE_DEMO_READ_ONLY=1 \
.venv/bin/uvicorn beanfeature_api.main:app --host 127.0.0.1 --port 8000 \
    > "$LOG_DIR/api.log" 2>&1 &
API_PID=$!
wait_for_local "$LOCAL_API/health" "Local API" "$API_PID"

echo "Starting worker..."
.venv/bin/beanfeature-worker > "$LOG_DIR/worker.log" 2>&1 &
WORKER_PID=$!

echo "Starting production Next.js..."
(
    cd "$ROOT/apps/web"
    export BEANFEATURE_INTERNAL_API_BASE_URL="$LOCAL_API"
    exec node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000
) > "$LOG_DIR/web.log" 2>&1 &
WEB_PID=$!
wait_for_local "$LOCAL_WEB" "Local Web" "$WEB_PID"

if curl --silent --fail --connect-timeout 3 --max-time 7 "$PUBLIC_API/health" -o /dev/null 2>/dev/null && \
   curl --silent --fail --connect-timeout 3 --max-time 7 "$PUBLIC_WEB" -o /dev/null 2>/dev/null && \
   [ "$SYSTEM_TUNNEL_PROCESS" -eq 1 ]; then
    TUNNEL_STATUS="CONNECTED"
else
    TUNNEL_STATUS="WARNING — public DNS/tunnel is not ready; local app is healthy"
fi

echo
echo "=================================================="
echo "     BeanFeature Lab — PRESENTATION READY"
echo "=================================================="
echo "Local:      $LOCAL_WEB"
echo "Public:     $PUBLIC_WEB"
echo "API:        $PUBLIC_API"
echo "API docs:   $PUBLIC_API/docs"
echo "Worker:     RUNNING"
echo "Cloudflare Named Tunnel: $TUNNEL_STATUS"
echo
echo "Press Ctrl+C to stop BeanFeature Lab."
echo "Cloudflare system tunnel will remain running."
echo "=================================================="

while true; do
    for pid in "$API_PID" "$WORKER_PID" "$WEB_PID"; do
        if ! kill -0 "$pid" 2>/dev/null; then
            echo "ERROR: A presentation process exited unexpectedly. See $LOG_DIR." >&2
            exit 1
        fi
    done
    sleep 2
done
