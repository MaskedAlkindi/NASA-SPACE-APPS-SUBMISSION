#!/usr/bin/env bash
# Pull the latest code and rebuild the online demo. Data (database, models, LLM runs) is kept.
set -euo pipefail
cd "$(dirname "$0")/../.."
git pull --ff-only
source deploy/digitalocean/.compose
docker compose $COMPOSE_FILES up -d --build
docker image prune -f >/dev/null
docker compose $COMPOSE_FILES ps
