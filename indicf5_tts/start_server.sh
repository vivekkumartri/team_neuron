#!/usr/bin/env bash
# Starts the IndicF5 API server on localhost:8001.
# Requires: `bash setup.sh` already run once.
set -euo pipefail
cd "$(dirname "$0")"

source .venv/bin/activate

# Idempotent: kill anything already bound to :8001 first. Without this, a
# rerun starts a second uvicorn that immediately dies with "address already
# in use" while the earlier (possibly stale/orphaned) one keeps answering
# health checks — looking exactly like the new process got killed, when
# really it just lost a port conflict.
EXISTING_PIDS=$(lsof -tiTCP:8001 -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$EXISTING_PIDS" ]; then
    echo "==> Port 8001 already in use by PID(s) $EXISTING_PIDS — stopping first"
    kill $EXISTING_PIDS 2>/dev/null || true
    sleep 1
fi

echo "==> Starting API server on :8001 (log: server.log)"
nohup uvicorn api_server:app --host 0.0.0.0 --port 8001 > server.log 2>&1 &
disown
SERVER_PID=$!
echo "    Server PID: $SERVER_PID"

echo "==> Waiting for server to become healthy..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8001/health > /dev/null 2>&1; then
        echo "    Server is up."
        break
    fi
    sleep 2
done

echo ""
echo "=================================================="
echo "Local URL: http://localhost:8001"
echo "Health check: http://localhost:8001/health"
echo "=================================================="
echo ""
echo "To stop: kill $SERVER_PID"
echo "(PID also saved to .server.pid)"
echo "$SERVER_PID" > .server.pid
