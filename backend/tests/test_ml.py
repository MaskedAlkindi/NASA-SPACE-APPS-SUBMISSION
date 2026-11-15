import numpy as np
import pandas as pd

from app.intelligence import models_service
from ml.datasets.synthetic import DEFAULT_CREW, Episode, SimConfig, generate_daily
from ml.models.features import anomaly_matrix


def _daily(episodes, days=40, seed=3):
    df = generate_daily([DEFAULT_CREW[0]], SimConfig(days=days, seed=seed, episodes=episodes))
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_models_available():
    models_service.ensure_trained()
    a, f, fc = models_service.detectors()
    assert a.available and f.available and fc.available


def test_anomaly_detects_injected_cardio_episode_and_explains_it():
    a, _, _ = models_service.detectors()
    daily = _daily([Episode("cardio_anomaly", 36, 3, 1.2, "AST-001")])
    res = a.score_days(daily)
    flagged_days = {r["date"] for r in res if r["is_anomaly"]}
    episode_days = {str(d.date()) for d in daily["date"].iloc[36:39]}
    assert flagged_days & episode_days
    flagged = next(r for r in res if r["date"] in flagged_days & episode_days)
    assert flagged["contributors"][0]["metric"] in ("resting_heart_rate", "hrv_sdnn")   # explanation names the cause
    assert "baseline_median" in flagged["contributors"][0]
    # early days lack a personal baseline and must say so instead of guessing
    assert res[0]["status"] == "insufficient_baseline"


def test_anomaly_quiet_on_nominal_history():
    a, _, _ = models_service.detectors()
    res = a.score_days(_daily([], seed=11))
    scored = [r for r in res if r["status"] == "scored"]
    assert sum(r["is_anomaly"] for r in scored) / len(scored) < 0.15


def test_baseline_excludes_current_day():
    df = _daily([])
    df.loc[df.index[-1], "resting_heart_rate"] = 120
    X, det = anomaly_matrix(df)
    assert det[-1]["resting_heart_rate"]["baseline"]["median"] < 80 and X[-1, 0] > 5


def test_fatigue_estimate_bounded_and_handles_missing():
    _, f, _ = models_service.detectors()
    df = _daily([Episode("fatigue_buildup", 30, 8, 1.2, "AST-001")])
    est = f.estimate_latest(df)
    assert est["status"] == "estimated" and 1 <= est["fatigue_estimate"] <= 7
    assert est["interval_80"][0] <= est["fatigue_estimate"] <= est["interval_80"][1]
    nominal = f.estimate_latest(_daily([]))
    assert est["fatigue_estimate"] > nominal["fatigue_estimate"]
    df2 = df.drop(columns=["workload_tlx", "sleep_efficiency"])
    est2 = f.estimate_latest(df2)
    assert est2["status"] == "estimated" and "workload_today" in est2["missing"]


def test_forecast_shape_and_insufficient_data():
    _, _, fc = models_service.detectors()
    df = _daily([])
    out = fc.forecast(df, "resting_heart_rate", horizon=7)
    assert out["status"] == "forecast" and len(out["points"]) == 7
    widths = [p["upper_80"] - p["lower_80"] for p in out["points"]]
    assert all(np.diff(widths) >= 0)  # uncertainty grows with horizon
    assert fc.forecast(df.head(5), "resting_heart_rate")["status"] == "insufficient_data"
    assert fc.forecast(df, "hrv_rmssd")["status"] == "insufficient_data"
