"""Versioned model artifact locations and loading."""
from __future__ import annotations

import json
import os
from pathlib import Path

import joblib

ARTIFACT_DIR = Path(os.getenv("HMT_ARTIFACT_DIR", Path(__file__).resolve().parents[1] / "artifacts"))

ANOMALY_VERSION = "anomaly-iforest-1.0.0"
FATIGUE_VERSION = "fatigue-hgb-1.0.0"
FORECAST_VERSION = "forecast-holt-1.0.0"

FILES = {
    ANOMALY_VERSION: "anomaly_iforest_v1.joblib",
    FATIGUE_VERSION: "fatigue_hgb_v1.joblib",
    FORECAST_VERSION: "forecast_holt_v1.json",
}


def path_for(version: str) -> Path:
    return ARTIFACT_DIR / FILES[version]


def save_joblib(version: str, obj) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    p = path_for(version)
    joblib.dump(obj, p)
    return p


def load_joblib(version: str):
    p = path_for(version)
    if not p.exists():
        return None
    return joblib.load(p)


def save_json(version_or_name: str, obj: dict) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    p = path_for(version_or_name) if version_or_name in FILES else ARTIFACT_DIR / version_or_name
    p.write_text(json.dumps(obj, indent=2, default=str))
    return p


def load_json(version_or_name: str) -> dict | None:
    p = path_for(version_or_name) if version_or_name in FILES else ARTIFACT_DIR / version_or_name
    if not p.exists():
        return None
    return json.loads(p.read_text())


def artifacts_present() -> bool:
    return all(path_for(v).exists() for v in FILES)
