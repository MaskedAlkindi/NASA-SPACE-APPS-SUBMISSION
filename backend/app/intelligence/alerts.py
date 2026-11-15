"""Alert engine: transparent rules + ML anomaly model.

Every alert stores the measurements that triggered it (``evidence``) so the UI
and the assistant can explain *why* it fired. Thresholds are demo defaults.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Alert
from app.intelligence import models_service
from app.intelligence.daily import latest_timestamp, load_measurements
from app.modules.environment.module import DEFAULT_LIMITS
from ml.models import artifacts
from ml.models.features import personal_baseline

ESCALATE = ("If you feel unwell (e.g. chest pain, fainting, breathing difficulty, severe headache), "
            "contact the flight surgeon / crew medical officer immediately.")


def _ev(metric, value, unit, baseline=None, z=None, note=None):
    e = {"metric": metric, "value": None if value is None else round(float(value), 2), "unit": unit}
    if baseline is not None:
        e["baseline_median"] = round(float(baseline), 2)
    if z is not None:
        e["z"] = round(float(z), 2)
    if note:
        e["note"] = note
    return e


def evaluate_astronaut(daily: pd.DataFrame, astronaut_id: str) -> list[dict]:
    """Return candidate alerts for the most recent day in ``daily``."""
    if daily.empty:
        return []
    daily = daily.sort_values("date").reset_index(drop=True)
    i = len(daily) - 1
    last = daily.iloc[i]
    day = str(pd.Timestamp(last["date"]).date())
    out: list[dict] = []

    def add(rule, severity, category, title, message, evidence, rec="", source="rule"):
        out.append({"astronaut_id": astronaut_id, "severity": severity, "category": category, "title": title,
                    "message": message, "evidence": evidence, "recommendation": rec,
                    "source": source if source != "rule" else f"rule:{rule}", "dedupe_key": f"{astronaut_id}:{rule}:{day}",
                    "observed_at": pd.Timestamp(last["date"]).to_pydatetime().replace(tzinfo=timezone.utc)})

    def val(m):
        return None if m not in daily.columns or pd.isna(last.get(m)) else float(last[m])

    # --- ML anomaly model --------------------------------------------------
    a, f, _ = models_service.detectors()
    if a.available:
        res = a.latest(daily)
        if res and res.get("is_anomaly"):
            top = res["contributors"][:3]
            parts = [f"{c['label'].lower()} {c['value']} vs usual {c['baseline_median']} ({c['direction']} baseline)" for c in top]
            add("ml_anomaly", "caution", "anomaly", "Unusual combination of measurements",
                "The anomaly model rates today as unusual compared with your own history: " + "; ".join(parts) + ".",
                [_ev(c["metric"], c["value"], "", c["baseline_median"], c["z"]) for c in top],
                "Re-check how you feel and repeat measurements; mention it at the next medical conference. " + ESCALATE,
                source=artifacts.ANOMALY_VERSION)

    # --- Cardiovascular ------------------------------------------------------
    rhr = val("resting_heart_rate")
    b = personal_baseline(daily, i, "resting_heart_rate")
    if rhr is not None and b:
        z = (rhr - b["median"]) / b["scale"]
        if z >= 2.5 and rhr - b["median"] >= 8:
            add("rhr_high", "caution", "cardiovascular", "Resting heart rate above your baseline",
                f"Resting heart rate is {rhr:.0f} bpm, {rhr - b['median']:.0f} bpm above your usual {b['median']:.0f} bpm.",
                [_ev("resting_heart_rate", rhr, "bpm", b["median"], z)],
                "Common non-medical causes include poor sleep, stress, dehydration or recent exercise. " + ESCALATE)
    hrv = val("hrv_sdnn")
    b = personal_baseline(daily, i, "hrv_sdnn")
    if hrv is not None and b:
        z = (hrv - b["median"]) / b["scale"]
        if z <= -2.5:
            add("hrv_low", "caution", "cardiovascular", "Heart-rate variability below your baseline",
                f"HRV (SDNN) is {hrv:.0f} ms versus your usual {b['median']:.0f} ms. Lower HRV often accompanies stress, fatigue or illness.",
                [_ev("hrv_sdnn", hrv, "ms", b["median"], z)], "Prioritise recovery and sleep; re-measure tomorrow morning.")
    spo2 = val("oxygen_saturation")
    if spo2 is not None and spo2 < 92:
        add("spo2_low", "warning", "cardiovascular", "Low blood-oxygen reading",
            f"Blood oxygen saturation reading of {spo2:.0f}% is below 92%.", [_ev("oxygen_saturation", spo2, "%")],
            "Re-measure at rest with good sensor contact. " + ESCALATE)
    sbp = val("blood_pressure_systolic")
    if sbp is not None and sbp >= 140:
        add("bp_high", "caution", "cardiovascular", "Elevated blood pressure reading",
            f"Systolic pressure {sbp:.0f} mmHg (>=140).", [_ev("blood_pressure_systolic", sbp, "mmHg")],
            "Repeat after 5 minutes seated rest and report to the medical officer if it persists.")

    # --- Sleep & fatigue -----------------------------------------------------
    if "sleep_duration" in daily.columns:
        s3 = daily["sleep_duration"].tail(3).dropna()
        if len(s3) == 3 and s3.mean() < 6.0:
            add("sleep_short_3n", "caution", "sleep", "Sustained short sleep",
                f"Average sleep over the last 3 nights is {s3.mean():.1f} h.",
                [_ev("sleep_duration", v, "h", note=f"night {k + 1}") for k, v in enumerate(s3.tolist())],
                "Sleep loss is a known spaceflight risk; consider protecting the next sleep period.")
        elif val("sleep_duration") is not None and val("sleep_duration") < 5.0:
            add("sleep_short_1n", "info", "sleep", "Short sleep last night",
                f"Recorded sleep was {val('sleep_duration'):.1f} h.", [_ev("sleep_duration", val("sleep_duration"), "h")])
    if "sleep_midpoint" in daily.columns:
        mids = daily["sleep_midpoint"].tail(5).dropna()
        if len(mids) >= 4 and float(np.std(mids)) > 1.2:
            add("sleep_irregular", "info", "sleep", "Irregular sleep timing",
                f"Sleep midpoint varied by ±{float(np.std(mids)):.1f} h over recent nights (circadian disruption indicator).",
                [_ev("sleep_midpoint", v, "h") for v in mids.tolist()], "Keep sleep and light schedules as regular as operations allow.")
    fat = val("fatigue_score")
    if fat is not None and fat >= 6:
        add("fatigue_selfreport", "warning", "fatigue", "High self-reported fatigue",
            f"Fatigue check-in score is {fat:.0f}/7.", [_ev("fatigue_score", fat, "score 1-7")],
            "Avoid safety-critical tasks without a cross-check and inform the flight surgeon / mission control.")
    elif f.available:
        est = f.estimate_latest(daily) or {}
        if est.get("status") == "estimated" and est["fatigue_estimate"] >= 5.0:
            add("fatigue_model", "caution", "fatigue", "Model estimates elevated fatigue",
                f"The fatigue simulation model estimates {est['fatigue_estimate']:.1f}/7 (80% range {est['interval_80'][0]}-{est['interval_80'][1]}) "
                "based on recent sleep and workload.",
                [_ev(k, v, "") for k, v in est["inputs"].items() if v is not None][:5],
                "This is a model estimate, not a measurement - complete a fatigue check-in to confirm.",
                source=artifacts.FATIGUE_VERSION)

    # --- Activity --------------------------------------------------------------
    if "exercise_minutes" in daily.columns:
        ex = daily["exercise_minutes"].dropna()
        if len(ex) >= 10:
            base = ex.iloc[:-3].tail(14).median()
            recent = ex.tail(3).mean()
            if base > 0 and recent < 0.5 * base:
                add("exercise_low", "info", "activity", "Exercise below usual routine",
                    f"Exercise averaged {recent:.0f} min/day over 3 days vs usual {base:.0f} min.",
                    [_ev("exercise_minutes", recent, "min", base)], "Exercise is a key countermeasure for bone, muscle and cardiovascular deconditioning.")

    # --- Vitals & metabolism (indicators named in the challenge brief) ------------
    temp = val("body_temperature")
    b = personal_baseline(daily, i, "body_temperature")
    if temp is not None:
        if temp >= 38.5:
            add("temp_high", "warning", "vitals", "High body temperature",
                f"Body temperature {temp:.1f} °C.", [_ev("body_temperature", temp, "°C", b["median"] if b else None)],
                "Re-measure, rest and drink fluids, and tell the crew medical officer. " + ESCALATE)
        elif b and temp - b["median"] >= 0.5 and (temp - b["median"]) / b["scale"] >= 2.5:
            add("temp_above_baseline", "caution", "vitals", "Body temperature above your usual",
                f"Body temperature {temp:.1f} °C vs your in-flight usual {b['median']:.1f} °C. Core temperature runs about "
                "1 °C higher in microgravity, so the tool compares with your own baseline rather than Earth fever cut-offs.",
                [_ev("body_temperature", temp, "°C", b["median"], (temp - b["median"]) / b["scale"])],
                "Can be an early sign of illness. Re-measure in an hour and note any symptoms.",
                source="rule:temp_above_baseline (NASA evidence: core-temperature)")
    glu = val("blood_glucose")
    if glu is not None:
        from app.intelligence.research import lab_reference_range
        ref = lab_reference_range("GLUCOSE") or (65.0, 99.0)
        if glu < 54:
            add("glucose_low", "warning", "vitals", "Low blood glucose", f"Blood glucose {glu:.0f} mg/dL.",
                [_ev("blood_glucose", glu, "mg/dL", note=f"lab reference {ref[0]:.0f}-{ref[1]:.0f}")],
                "Eat or drink something with sugar now and re-check in 15 minutes. " + ESCALATE)
        elif glu >= 140:
            add("glucose_high", "caution", "vitals", "High blood glucose",
                f"Blood glucose {glu:.0f} mg/dL. Spaceflight can raise insulin resistance even when glucose looks normal.",
                [_ev("blood_glucose", glu, "mg/dL", note=f"lab reference {ref[0]:.0f}-{ref[1]:.0f}")],
                "Re-check fasting tomorrow morning and report the trend to the flight surgeon.")
        elif not ref[0] <= glu <= ref[1]:
            add("glucose_out_of_range", "info", "vitals", "Blood glucose outside the lab reference range",
                f"Blood glucose {glu:.0f} mg/dL; the reference range in NASA's Inspiration4 lab data (OSD-575) is "
                f"{ref[0]:.0f}-{ref[1]:.0f} mg/dL.", [_ev("blood_glucose", glu, "mg/dL", note=f"reference {ref[0]:.0f}-{ref[1]:.0f}")],
                "One reading is not a diagnosis; check that it was a fasting measurement.",
                source="rule:glucose_out_of_range (NASA OSD-575 reference range)")
    if "body_mass" in daily.columns:
        bm = daily["body_mass"].dropna()
        if len(bm) >= 14:
            start = float(bm.head(7).mean())
            now = float(bm.tail(3).mean())
            loss = (start - now) / start * 100
            days = (pd.Timestamp(daily["date"].iloc[-1]) - pd.Timestamp(daily.loc[bm.index[0], "date"])).days
            expected = 2.4 * days / 100
            if loss >= max(5.0, expected * 2):
                add("mass_loss", "caution", "nutrition", "Body mass falling faster than expected",
                    f"Body mass down {loss:.1f}% over {days} days ({start:.1f} → {now:.1f} kg). NASA's spaceflight average "
                    f"is about 2.4% per 100 days (≈{expected:.1f}% for this period).",
                    [_ev("body_mass", now, "kg", start, note=f"-{loss:.1f}%")],
                    "Check food and fluid intake against your plan; discuss with the crew medical officer.",
                    source="rule:mass_loss (NASA evidence: body-mass-loss)")

    # --- Wellbeing -------------------------------------------------------------
    mood, stress = val("mood_score"), val("stress_score")
    if mood is not None and stress is not None and mood <= 2 and stress >= 8:
        add("mood_stress", "caution", "wellbeing", "Low mood with high stress",
            f"Mood {mood:.0f}/5 and stress {stress:.0f}/10 reported.",
            [_ev("mood_score", mood, "score 1-5"), _ev("stress_score", stress, "score 1-10")],
            "Consider talking with a crewmate or the behavioural-health support team.")
    rt = val("reaction_time")
    b = personal_baseline(daily, i, "reaction_time")
    if rt is not None and b and (rt - b["median"]) / max(b["scale"], 8) >= 2.5:
        add("reaction_slow", "info", "wellbeing", "Slower reaction time than usual",
            f"Reaction-time test mean {rt:.0f} ms vs usual {b['median']:.0f} ms.", [_ev("reaction_time", rt, "ms", b["median"])],
            "Often linked to fatigue or sleep loss; retest when rested.")
    return out


def evaluate_environment(db: Session) -> list[dict]:
    latest = latest_timestamp(db, None)
    if latest is None:
        return []
    raw = load_measurements(db, None, since=latest - timedelta(minutes=1))
    if raw.empty:
        return []
    latest_ts = raw["timestamp"].max()
    cur = raw[raw["timestamp"] == latest_ts].set_index("metric")["value"]
    out = []
    when = latest_ts.to_pydatetime()
    day = str(latest_ts.date())

    def add(rule, sev, title, msg, metric, value, unit, rec):
        out.append({"astronaut_id": None, "severity": sev, "category": "environment", "title": title, "message": msg,
                    "evidence": [_ev(metric, value, unit)], "recommendation": rec, "source": f"rule:{rule}",
                    "dedupe_key": f"env:{rule}:{sev}:{day}", "observed_at": when})

    co2 = cur.get("cabin_co2")
    if co2 is not None:
        lim = DEFAULT_LIMITS["cabin_co2"]
        if co2 >= lim["warning"]:
            add("co2", "warning", "Cabin CO₂ high", f"CO₂ partial pressure {co2:.2f} mmHg (demo warning limit {lim['warning']}).",
                "cabin_co2", co2, "mmHg", "Check CO₂ removal system status; watch for headache or reduced concentration.")
        elif co2 >= lim["caution"]:
            add("co2", "caution", "Cabin CO₂ elevated", f"CO₂ partial pressure {co2:.2f} mmHg (demo caution limit {lim['caution']}).",
                "cabin_co2", co2, "mmHg", "Monitor trend; ensure ventilation near crew sleep stations.")
    rad = cur.get("radiation_dose_rate")
    if rad is not None:
        lim = DEFAULT_LIMITS["radiation_dose_rate"]
        sev = "warning" if rad >= lim["warning"] else ("caution" if rad >= lim["caution"] else None)
        if sev:
            add("radiation", sev, "Elevated radiation dose rate", f"Dose rate {rad:.1f} µGy/h (demo {sev} limit {lim[sev]}).",
                "radiation_dose_rate", rad, "µGy/h", "Follow mission radiation procedures (e.g. move to shielded area if directed).")
    for m in ("cabin_temperature", "cabin_humidity", "cabin_pressure"):
        v = cur.get(m)
        lim = DEFAULT_LIMITS[m]
        if v is not None and not (lim["low"] <= v <= lim["high"]):
            add(m, "caution", f"{m.replace('_', ' ').title()} out of range",
                f"{v:.1f} {lim['unit']} (demo range {lim['low']}-{lim['high']}).", m, v, lim["unit"], "Check habitat environmental control settings.")
    return out


def persist(db: Session, candidates: list[dict], data_class: str = "simulated") -> list[Alert]:
    created = []
    for c in candidates:
        exists = db.execute(select(Alert.id).where(Alert.dedupe_key == c["dedupe_key"])).first()
        if exists:
            continue
        al = Alert(**c, data_class=data_class)
        db.add(al)
        created.append(al)
    if created:
        db.commit()
    return created
