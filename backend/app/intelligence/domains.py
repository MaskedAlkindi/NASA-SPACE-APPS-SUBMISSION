"""Domain analysers (cardiovascular, sleep, activity, wellbeing, environment).

Each analyser is a pure function of a daily frame, so domains can be tested or
replaced independently. Output is the structured "health summary" used by the
dashboard and as the ONLY health context sent to the assistant.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.schemas.metrics import METRICS

DOMAIN_METRICS = {
    "cardiovascular": ["resting_heart_rate", "hrv_sdnn", "hrv_rmssd", "blood_pressure_systolic",
                       "blood_pressure_diastolic", "oxygen_saturation"],
    "sleep": ["sleep_duration", "sleep_efficiency", "sleep_midpoint", "fatigue_score"],
    "activity": ["steps", "exercise_minutes", "active_energy"],
    "wellbeing": ["mood_score", "stress_score", "workload_tlx", "reaction_time"],
    "vitals": ["body_temperature", "blood_glucose", "body_mass"],
}
# direction in which a change is "worse" (for wording only - not a diagnosis)
WORSE_IF = {"resting_heart_rate": "up", "hrv_sdnn": "down", "hrv_rmssd": "down", "sleep_duration": "down",
            "sleep_efficiency": "down", "fatigue_score": "up", "steps": "down", "exercise_minutes": "down",
            "mood_score": "down", "stress_score": "up", "workload_tlx": "up", "reaction_time": "up",
            "blood_pressure_systolic": "up", "blood_pressure_diastolic": "up", "oxygen_saturation": "down",
            "body_temperature": "up", "blood_glucose": "up", "body_mass": "down"}


def metric_summary(daily: pd.DataFrame, metric: str) -> dict:
    mdef = METRICS[metric]
    base = {"metric": metric, "label": mdef.label, "unit": mdef.unit}
    if metric not in daily.columns or daily[metric].dropna().empty:
        return {**base, "status": "no_data"}
    s = daily.set_index("date")[metric].dropna()
    latest = float(s.iloc[-1])
    recent = s.tail(7)
    baseline = s.iloc[:-7].tail(28) if len(s) > 14 else s
    med = float(baseline.median())
    p10, p90 = float(baseline.quantile(0.1)), float(baseline.quantile(0.9))
    slope = float(np.polyfit(np.arange(len(recent)), recent.to_numpy(), 1)[0]) if len(recent) >= 4 else 0.0
    status = "within_usual_range"
    if latest > p90 + 1e-9:
        status = "above_usual_range"
    elif latest < p10 - 1e-9:
        status = "below_usual_range"
    worse = WORSE_IF.get(metric)
    concern = (status == "above_usual_range" and worse == "up") or (status == "below_usual_range" and worse == "down")
    return {**base, "status": status, "concern": concern, "latest": round(latest, 2),
            "latest_date": str(pd.Timestamp(s.index[-1]).date()), "avg_7d": round(float(recent.mean()), 2),
            "baseline_median": round(med, 2), "baseline_range": [round(p10, 2), round(p90, 2)],
            "baseline_days": int(len(baseline)), "trend_per_day_7d": round(slope, 3),
            "delta_vs_baseline_pct": round((float(recent.mean()) - med) / med * 100, 1) if med else None}


def sleep_extras(daily: pd.DataFrame) -> dict:
    out = {}
    if "sleep_midpoint" in daily.columns:
        mids = daily["sleep_midpoint"].dropna().tail(7)
        if len(mids) >= 3:
            out["sleep_timing_variability_h"] = round(float(np.std(mids)), 2)
            out["circadian_disruption"] = bool(np.std(mids) > 1.0)
    if "sleep_duration" in daily.columns:
        sd = daily["sleep_duration"].dropna().tail(7)
        if len(sd) >= 3:
            out["sleep_debt_7d_h_vs_7_5h"] = round(float(np.maximum(0, 7.5 - sd).sum()), 1)
    return out


def activity_extras(daily: pd.DataFrame, target_min: float = 90.0) -> dict:
    if "exercise_minutes" not in daily.columns:
        return {}
    ex = daily["exercise_minutes"].dropna().tail(7)
    if ex.empty:
        return {}
    return {"exercise_target_min": target_min,
            "training_adherence_7d_pct": round(float((ex >= target_min).mean() * 100), 0)}


def health_summary(daily: pd.DataFrame) -> dict:
    domains = {}
    for dom, metrics in DOMAIN_METRICS.items():
        items = [metric_summary(daily, m) for m in metrics]
        items = [i for i in items if i["status"] != "no_data"] or items[:1]
        concerns = [i["label"] for i in items if i.get("concern")]
        domains[dom] = {"metrics": items, "concerns": concerns,
                        "status": "attention" if concerns else ("nominal" if any(i["status"] != "no_data" for i in items) else "no_data")}
    domains["sleep"].update(sleep_extras(daily))
    domains["activity"].update(activity_extras(daily))
    missing = [m for ms in DOMAIN_METRICS.values() for m in ms
               if m not in daily.columns or daily[m].dropna().empty]
    as_of = str(pd.Timestamp(daily["date"].max()).date()) if not daily.empty else None
    return {"as_of": as_of, "days_of_data": int(len(daily)), "domains": domains, "unavailable_metrics": missing}


def environment_summary(raw: pd.DataFrame) -> dict:
    if raw.empty:
        return {"status": "no_data", "metrics": []}
    out = []
    for metric, g in raw.groupby("metric"):
        g = g.sort_values("timestamp")
        mdef = METRICS.get(metric)
        if not mdef:
            continue
        last24 = g[g["timestamp"] >= g["timestamp"].max() - pd.Timedelta(hours=24)]
        out.append({"metric": metric, "label": mdef.label, "unit": mdef.unit, "latest": round(float(g["value"].iloc[-1]), 2),
                    "latest_at": g["timestamp"].iloc[-1].isoformat(), "mean_24h": round(float(last24["value"].mean()), 2),
                    "max_24h": round(float(last24["value"].max()), 2), "data_class": g["data_class"].iloc[-1]})
    return {"status": "ok", "metrics": out}
