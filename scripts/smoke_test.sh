#!/usr/bin/env bash
# End-to-end smoke test against the running Docker stack. Fails loudly (non-zero) on any problem.
#   docker compose up -d --build && ./scripts/smoke_test.sh
set -euo pipefail
API="${API:-http://localhost:8000}"
WEB="${WEB:-http://localhost:8080}"
PASS="${DEMO_PASSCODE:-hmt-demo}"
PY=$(command -v python3 || command -v python)
fail() { echo "FAIL: $*" >&2; exit 1; }

echo "Waiting for API health..."
for _ in $(seq 1 60); do curl -fs "$API/api/v1/health" >/dev/null 2>&1 && break; sleep 3; done
curl -fs "$API/api/v1/health" | grep -q '"database":true' || fail "API health"
curl -fs -o /dev/null "$WEB/" || fail "website not reachable at $WEB"
curl -fs "$WEB/api/v1/health" >/dev/null || fail "nginx -> API proxy"

TOKEN=$(curl -fs -X POST "$API/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"mission-control\",\"passcode\":\"$PASS\"}" | "$PY" -c 'import sys,json;print(json.load(sys.stdin)["access_token"])') || fail "login"
H="Authorization: Bearer $TOKEN"

n=$(curl -fs "$API/api/v1/astronauts/AST-001/measurements?metric=heart_rate&days=3" -H "$H" | "$PY" -c 'import sys,json;print(len(json.load(sys.stdin)["items"]))')
[ "$n" -gt 0 ] || fail "no demo measurements"
curl -fs "$API/api/v1/astronauts/AST-004/predictions" -H "$H" | grep -q '"status":"scored"' || fail "anomaly inference"
curl -fs "$API/api/v1/astronauts/AST-004/alerts" -H "$H" | grep -q '"evidence"' || fail "alerts"
curl -fs -X POST "$API/api/v1/assistant/chat" -H "$H" -H 'Content-Type: application/json' \
  -d '{"astronaut_id":"AST-002","message":"How am I doing today?"}' | grep -q '"answer"' || fail "assistant"
curl -fs "$API/api/v1/research/datasets" -H "$H" | grep -q 'OSD-' || fail "NASA datasets (import may still be running; retry in 30 s)"
echo "OK: API, website, demo data, ML inference, alerts, assistant and NASA research all responded."
