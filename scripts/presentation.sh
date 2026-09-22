#!/bin/bash

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOG_DIR="/tmp/beanfeature-presentation"
mkdir -p "$LOG_DIR"

API_LOG="$LOG_DIR/api.log"
API_TUNNEL_LOG="$LOG_DIR/api-tunnel.log"
WEB_LOG="$LOG_DIR/web.log"
WEB_TUNNEL_LOG="$LOG_DIR/web-tunnel.log"
WORKER_LOG="$LOG_DIR/worker.log"

cleanup() {
    trap - INT TERM EXIT
    echo
    echo "Stopping BeanFeature Lab..."

    [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null || true
    [ -n "$WORKER_PID" ] && kill "$WORKER_PID" 2>/dev/null || true
    [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null || true
    [ -n "$API_TUNNEL_PID" ] && kill "$API_TUNNEL_PID" 2>/dev/null || true
    [ -n "$WEB_TUNNEL_PID" ] && kill "$WEB_TUNNEL_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

for port in 8000 3000; do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN -t | grep -q .; then
        echo "ERROR: Local port $port is occupied. Stop that process before presentation."
        exit 1
    fi
done

echo "Applying migrations..."
.venv/bin/alembic upgrade head

echo "Starting API..."

BEANFEATURE_CORS_ORIGINS="http://127.0.0.1:3000,http://localhost:3000" \
BEANFEATURE_DEMO_READ_ONLY=1 \
.venv/bin/uvicorn beanfeature_api.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    > "$API_LOG" 2>&1 &

API_PID=$!

echo "Starting worker..."

.venv/bin/beanfeature-worker \
    > "$WORKER_LOG" 2>&1 &

WORKER_PID=$!

sleep 2

echo "Starting API tunnel..."

cloudflared tunnel \
    --protocol http2 \
    --url http://127.0.0.1:8000 \
    > "$API_TUNNEL_LOG" 2>&1 &

API_TUNNEL_PID=$!

API_URL=""

for i in {1..30}; do
    API_URL=$(grep -Eo 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$API_TUNNEL_LOG" | head -1 || true)

    if [ -n "$API_URL" ]; then
        break
    fi

    sleep 1
done

if [ -z "$API_URL" ]; then
    echo "ERROR: Could not obtain API tunnel URL."
    echo "See $API_TUNNEL_LOG"
    exit 1
fi

echo "API: $API_URL"

echo "Building frontend..."

cd "$ROOT/apps/web"

BEANFEATURE_INTERNAL_API_BASE_URL="http://127.0.0.1:8000" \
NEXT_PUBLIC_API_BASE_URL="" \
NEXT_PUBLIC_DEMO_READ_ONLY=1 \
npm run build > "$WEB_LOG" 2>&1
printf 'quick\n' > "$ROOT/apps/web/.next/beanfeature-named-build.sha256"

echo "Starting frontend..."

BEANFEATURE_INTERNAL_API_BASE_URL="http://127.0.0.1:8000" \
node "$ROOT/apps/web/node_modules/next/dist/bin/next" start --hostname 127.0.0.1 --port 3000 \
    > "$WEB_LOG" 2>&1 &

WEB_PID=$!

cd "$ROOT"

sleep 3

echo "Starting frontend tunnel..."

cloudflared tunnel \
    --protocol http2 \
    --url http://127.0.0.1:3000 \
    > "$WEB_TUNNEL_LOG" 2>&1 &

WEB_TUNNEL_PID=$!

WEB_URL=""

for i in {1..30}; do
    WEB_URL=$(grep -Eo 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$WEB_TUNNEL_LOG" | head -1 || true)

    if [ -n "$WEB_URL" ]; then
        break
    fi

    sleep 1
done

if [ -z "$WEB_URL" ]; then
    echo "ERROR: Could not obtain frontend tunnel URL."
    echo "See $WEB_TUNNEL_LOG"
    exit 1
fi

echo
echo "=================================================="
echo "          BeanFeature Lab is ONLINE"
echo "=================================================="
echo
echo "PUBLIC SITE:"
echo "$WEB_URL"
echo
echo "FEATURE BUDGET:"
echo "$WEB_URL/feature-budget"
echo
echo "PUBLIC API:"
echo "$API_URL"
echo
echo "API DOCS:"
echo "$API_URL/docs"
echo
echo "Press Ctrl+C to stop everything."
echo "=================================================="

while true; do
    sleep 3600
done
