#!/usr/bin/env bash
# Stops the API server + ngrok tunnel started by start_server.sh
cd "$(dirname "$0")"

if [ -f .server.pid ]; then
    kill $(cat .server.pid) 2>/dev/null && echo "Stopped." || echo "Already stopped."
    rm -f .server.pid
else
    pkill -f "uvicorn api_server" 2>/dev/null
    pkill -f "ngrok http" 2>/dev/null
    echo "Stopped (fallback pkill)."
fi
