#!/usr/bin/env bash
# CareerLoop SSE scan terminal — starts scan, prints every event live
# Usage: ./scripts/sse_scan.sh
set -e

BASE="http://localhost:8001"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../.env"

# Load env
[ -f "$ENV_FILE" ] && export $(grep -v '^#' "$ENV_FILE" | xargs)

# Generate JWT for test user
UID_VAL="730d5bab-2587-4507-a16a-70cd662d59c2"
TOKEN=$("$SCRIPT_DIR/../.venv/bin/python3.14" -c "
import jwt, time, os
secret = os.getenv('SUPABASE_JWT_SECRET')
print(jwt.encode({'sub':'$UID_VAL','email':'siddharth.swami99@gmail.com',
  'role':'authenticated','aud':'authenticated',
  'iat':int(time.time()),'exp':int(time.time())+7200}, secret, algorithm='HS256'))
")

echo "▶ Starting scan..."
SCAN_RESP=$(curl -s -X POST "$BASE/v1/scans/start" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")

RUN_ID=$(echo "$SCAN_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['run_id'])" 2>/dev/null)
if [ -z "$RUN_ID" ]; then
  echo "ERROR starting scan: $SCAN_RESP"
  exit 1
fi

echo "✓ Scan started — run_id=$RUN_ID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Streaming events (Ctrl+C to stop)  "
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Subscribe to SSE stream
curl -sN --no-buffer \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: text/event-stream" \
  "$BASE/v1/scans/$RUN_ID/events" | while IFS= read -r line; do
    if [[ "$line" == data:* ]]; then
      PAYLOAD="${line#data: }"
      TYPE=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('event_type','EVENT'))" 2>/dev/null)
      MSG=$(echo "$PAYLOAD"  | python3 -c "import sys,json; d=json.loads(sys.stdin.read()); print(d.get('message',''))" 2>/dev/null)
      TS=$(date '+%H:%M:%S')
      
      # Colour by event type
      case "$TYPE" in
        SOURCE_SCANNING|SCAN_STARTED) echo "[$TS] 🔍 $TYPE  $MSG" ;;
        JOB_FOUND|CANDIDATE_MATCHED)  echo "[$TS] ✅ $TYPE  $MSG" ;;
        JOB_REJECTED)                 echo "[$TS] ❌ $TYPE  $MSG" ;;
        BRIEF_CREATED|SCAN_COMPLETED) echo "[$TS] 🎯 $TYPE  $MSG" ;;
        FILTER_SUMMARY)               echo "[$TS] 📊 $TYPE  $MSG" ;;
        CACHE_HIT)                    echo "[$TS] ⚡ $TYPE  $MSG" ;;
        done)                         echo "[$TS] ✓ DONE"; break ;;
        *)                            echo "[$TS]    $TYPE  $MSG" ;;
      esac
    fi
  done
