#!/usr/bin/env bash
# Reproducibly retrain all models locally (writes ml/artifacts/*). Requires backend/requirements.txt installed.
set -euo pipefail
cd "$(dirname "$0")/.."
python -m ml.training.train_all
