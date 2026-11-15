"""Runs the three ML models for an astronaut. Works fully offline (no LLM involved)."""
from __future__ import annotations

import logging
from functools import lru_cache

import pandas as pd

from ml.models import anomaly, artifacts, fatigue, forecast

log = logging.getLogger("hmt.models")
FORECAST_METRICS = ["resting_heart_rate", "sleep_duration", "hrv_sdnn"]


@lru_cache
def detectors():
    return anomaly.AnomalyDetector(), fatigue.FatigueModel(), forecast.TrendForecaster()


def reload_models():
    detectors.cache_clear()
    return detectors()


def ensure_trained() -> bool:
    """Train artifacts on first start if missing (takes ~20-40 s)."""
    if artifacts.artifacts_present():
        return False
    log.warning("model artifacts missing in %s - training now", artifacts.ARTIFACT_DIR)
    from ml.training.train_all import main
    main()
    reload_models()
    return True


def model_catalog() -> list[dict]:
    a, f, fc = detectors()
    report = artifacts.load_json("metrics_report.json") or {}
    return [
        {"id": artifacts.ANOMALY_VERSION, "name": "Personalised anomaly detection", "type": "Isolation Forest on personal-baseline z-scores",
         "available": a.available, "training_data": "simulated", "metrics": report.get(artifacts.ANOMALY_VERSION),
         "inputs": anomaly.ANOMALY_FEATURES, "limitations": anomaly.LIMITATIONS},
        {"id": artifacts.FATIGUE_VERSION, "name": "Fatigue estimation (simulation model)", "type": "Histogram gradient boosting regressor",
         "available": f.available, "training_data": "simulated labels", "metrics": report.get(artifacts.FATIGUE_VERSION),
         "inputs": fatigue.FATIGUE_FEATURES, "limitations": fatigue.LIMITATIONS},
        {"id": artifacts.FORECAST_VERSION, "name": "Health trend forecasting", "type": "Damped Holt exponential smoothing",
         "available": fc.available, "training_data": "parameters selected on simulated backtests",
         "metrics": report.get(artifacts.FORECAST_VERSION), "inputs": FORECAST_METRICS, "limitations": forecast.LIMITATIONS},
    ]


def predictions(daily: pd.DataFrame, history_days: int = 21) -> dict:
    a, f, fc = detectors()
    out: dict = {"models": {}}
    if a.available and not daily.empty:
        scored = a.score_days(daily)
        out["anomaly"] = {"model_version": artifacts.ANOMALY_VERSION, "latest": scored[-1] if scored else None,
                          "history": [{"date": s["date"], "score": s["score"], "is_anomaly": s["is_anomaly"],
                                       "percentile": s.get("score_percentile")} for s in scored[-history_days:]],
                          "limitations": anomaly.LIMITATIONS}
    else:
        out["anomaly"] = {"model_version": artifacts.ANOMALY_VERSION, "status": "unavailable" if not a.available else "no_data"}
    if f.available and not daily.empty:
        out["fatigue"] = {"model_version": artifacts.FATIGUE_VERSION, **(f.estimate_latest(daily) or {}),
                          "limitations": fatigue.LIMITATIONS}
    else:
        out["fatigue"] = {"model_version": artifacts.FATIGUE_VERSION, "status": "unavailable" if not f.available else "no_data"}
    out["forecasts"] = {"model_version": artifacts.FORECAST_VERSION, "limitations": forecast.LIMITATIONS,
                        "series": [fc.forecast(daily, m) for m in FORECAST_METRICS] if not daily.empty else []}
    return out
