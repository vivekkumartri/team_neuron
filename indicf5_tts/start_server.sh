#!/usr/bin/env bash
# Starts the IndicF5 API server + an ngrok tunnel, and prints the public URL.
# Requires: `bash setup.sh` already run once, and `ngrok config add-authtoken <token>` already done.
set -euo pipefail
cd "$(dirname "$0")"

source .venv/bin/activate

echo "==> Starting API server on :8000 (log: server.log)"
nohup uvicorn api_server:app --host 0.0.0.0 --port 8000 > server.log 2>&1 &
SERVER_PID=$!
echo "    Server PID: $SERVER_PID"

echo "==> Waiting for server to become healthy..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "    Server is up."
        break
    fi
    sleep 2
done

if ! command -v ngrok &> /dev/null; then
    echo "ngrok not found. Install with: brew install ngrok"
    echo "Then run: ngrok config add-authtoken <your-token>"
    exit 1
fi

echo "==> Starting ngrok tunnel (log: ngrok.log)"
nohup ngrok http 8000 --log stdout > ngrok.log 2>&1 &
NGROK_PID=$!
echo "    ngrok PID: $NGROK_PID"

sleep 4
PUBLIC_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "")

echo ""
echo "=================================================="
if [ -n "$PUBLIC_URL" ]; then
    echo "Public URL: $PUBLIC_URL"
    echo "Health check: $PUBLIC_URL/health"
else
    echo "Could not fetch public URL automatically."
    echo "Check manually: curl http://localhost:4040/api/tunnels"
fi
echo "=================================================="
echo ""
echo "To stop: kill $SERVER_PID $NGROK_PID"
echo "(PIDs also saved to .server.pid)"
echo "$SERVER_PID $NGROK_PID" > .server.pid
