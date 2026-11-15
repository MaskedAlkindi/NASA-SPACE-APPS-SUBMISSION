#!/usr/bin/env bash
# Start the MQTT live-data module and wire its topics into the API.
#   ./scripts/mqtt_sim.sh          # publish + assign simulated topics
#   ./scripts/mqtt_sim.sh down
#   ./scripts/mqtt_sim.sh logs
# The main stack must already be up (docker compose up -d).
set -euo pipefail
cd "$(dirname "$0")/.."
API="${API:-http://localhost:8000}"
PASS="${DEMO_PASSCODE:-hmt-demo}"
BROKER_HOST="${MQTT_BROKER_HOST:-mosquitto}"
ACTION="${1:-up}"
PY=$(command -v python3 || command -v python)

case "$ACTION" in
  down)
    docker compose --profile mqtt-sim stop mqtt-sim
    exit 0
    ;;
  logs)
    docker compose --profile mqtt-sim logs -f mqtt-sim
    exit 0
    ;;
  up) ;;
  *) echo "usage: $0 [up|down|logs]" >&2; exit 1 ;;
esac

docker compose --profile mqtt-sim up -d --build mqtt-sim

echo "Waiting for API at $API ..."
ready=0
for _ in $(seq 1 40); do
  curl -fs "$API/api/v1/health" >/dev/null 2>&1 && ready=1 && break
  sleep 2
done
[ "$ready" = 1 ] || { echo "API not reachable. Start the stack first: docker compose up -d" >&2; exit 1; }

TOKEN=$(curl -fs -X POST "$API/api/v1/auth/login" -H 'Content-Type: application/json' \
  -d "{\"username\":\"mission-control\",\"passcode\":\"$PASS\"}" | "$PY" -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')

curl -fs -X POST "$API/api/v1/mqtt/sim-pipeline" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"host\":\"$BROKER_HOST\",\"port\":1883}"
echo
echo "Simulated habitat readings are publishing. Open Habitat sensors — every value is labelled simulated."
