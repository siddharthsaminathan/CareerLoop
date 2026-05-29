#!/bin/bash
# Start the CareerLoop API server with timestamped log file.
# Usage: ./start_api.sh [--no-tail]
#
# Logs go to: logs/api_YYYY-MM-DD_HH-MM-SS.log
# Live tail is shown in the terminal unless --no-tail is passed.
# Server runs on port 8001 (Telegram webhook stays on 8000).

set -e
cd "$(dirname "$0")"

# Load env (the app also self-loads .env via python-dotenv — belt and suspenders)
set -a; [ -f .env ] && source .env; set +a

# Schema already exists in the DB — skip re-running DDL on every boot (faster startup).
export CAREERLOOP_SKIP_SCHEMA_INIT="${CAREERLOOP_SKIP_SCHEMA_INIT:-true}"

# NOTE: --reload below is for LOCAL DEV. For production / load (100 users) use:
#   gunicorn careerloop_api.main:app -k uvicorn.workers.UvicornWorker -w 4 --bind 0.0.0.0:8001
# (multi-worker; see docs/handoffs for the concurrency-hardening checklist).

LOGDIR="logs"
mkdir -p "$LOGDIR"

TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOGFILE="$LOGDIR/api_${TIMESTAMP}.log"

echo "Starting CareerLoop API..."
echo "  Port    : 8001"
echo "  Log     : $LOGFILE"
echo "  Docs    : http://localhost:8001/docs"
echo ""

# Kill any existing instance on 8001
EXISTING=$(lsof -ti tcp:8001 2>/dev/null || true)
if [ -n "$EXISTING" ]; then
  echo "Killing existing process on port 8001 (PID $EXISTING)..."
  kill "$EXISTING" 2>/dev/null || true
  sleep 1
fi

# Write a header into the log
{
  echo "========================================"
  echo "CareerLoop API — started at $TIMESTAMP"
  echo "========================================"
} >> "$LOGFILE"

# Start uvicorn, pipe stdout+stderr to log
.venv/bin/uvicorn careerloop_api.main:app \
  --host 0.0.0.0 \
  --port 8001 \
  --reload \
  --log-level info \
  >> "$LOGFILE" 2>&1 &

SERVER_PID=$!
echo "Server PID: $SERVER_PID  (logs → $LOGFILE)"
echo "$SERVER_PID" > "$LOGDIR/api.pid"

# Wait for the server to come up
for i in $(seq 1 15); do
  if curl -s http://127.0.0.1:8001/health >/dev/null 2>&1; then
    echo "Server is UP ✓"
    echo ""
    break
  fi
  sleep 1
done

# Tail the log live (skip if --no-tail)
if [[ "$1" != "--no-tail" ]]; then
  echo "--- live log (Ctrl+C to stop tailing, server keeps running) ---"
  tail -f "$LOGFILE"
fi
