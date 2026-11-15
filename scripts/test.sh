#!/usr/bin/env bash
# Run the backend test suite inside the API image (same Python 3.12 environment as production).
# Exits non-zero if any test fails.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose build api
docker compose run --rm --no-deps -e DATABASE_URL= api python -m pytest -q tests
