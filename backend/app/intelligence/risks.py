"""Per-astronaut view of NASA's Human Research Program risks.

Built only from (a) what the tool actually measures and (b) the verified facts in the
challenge resources. Three small published-number models are included:
  * radiation: cumulative absorbed dose vs NASA's ISS range scaled to mission length
  * bone: expected bone-density loss from NASA's average monthly rate
  * nutrition: body-mass change vs NASA's average loss per 100 days
These are references and projections, not measurements of the risk itself.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Alert, Mission
from app.intelligence.daily import astronaut_daily, latest_timestamp, load_measurements
from app.intelligence.domains import metric_summary
from app.modules.nasa_hrp.module import load
from app.schemas.metrics import METRICS

STATUS_ORDER = {"attention": 0, "watch": 1, "ok": 2, "no_data": 3, "clinical_exam": 4, "not_monitored": 5}


def _evidence(k: dict, ids: list[str]) -> list[dict]:
    out = []
    for e in k["evidence"]:
        if e["id"] in ids:
            url = e["source_url"] + (f"#page={e['page']}" if e.get("page") else "")
            out.append({"id": e["id"], "statement": e["statement"], "quote": e["quote"], "source": e["source"],
                        "page": e.get("page"), "url": url})
    return out


def _ev_value(k: dict, eid: str, key: str):
    return next((e["values"][key] for e in k["evidence"] if e["id"] == eid), None)


def mission_day(db: Session, astronaut_id: str) -> int | None:
    m = db.execute(select(Mission)).scalars().first()
    ts = latest_timestamp(db, astronaut_id)
    if not m or ts is None:
        return None
    return (ts.date() - m.start_date).days + 1


def radiation_model(db: Session, k: dict, day: int | None) -> dict | None:
    latest = latest_timestamp(db, None)
    if latest is None or not day:
        return None
    raw = load_measurements(db, None, ["radiation_dose_rate"], since=latest - timedelta(days=3))
    if raw.empty:
        return None
    rate = float(raw["value"].mean())                       # µGy/h
    cumulative = rate * 24 * day / 1000                     # mGy, assumes the recent rate held all mission
    lo, hi = _ev_value(k, "radiation-dose-iss", "iss_6mo_mgy_low"), _ev_value(k, "radiation-dose-iss", "iss_6mo_mgy_high")
    exp_lo, exp_hi = lo * day / 182.5, hi * day / 182.5
    return {"model": "cumulative absorbed dose (estimate)", "mean_rate_uGy_h": round(rate, 1),
            "cumulative_mGy": round(cumulative, 1), "nasa_reference_mGy_for_this_duration": [round(exp_lo, 1), round(exp_hi, 1)],
            "above_reference": cumulative > exp_hi,
            "method": "recent mean habitat dose rate x hours since mission start; reference = NASA's 30-120 mGy per "
                      "six-month ISS stay scaled to the mission day",
            "evidence": ["radiation-dose-iss", "neutron-share"]}


def bone_model(daily: pd.DataFrame, k: dict, day: int | None) -> dict | None:
    if not day:
        return None
    lo, hi = _ev_value(k, "bone-loss-rate", "monthly_loss_pct_low"), _ev_value(k, "bone-loss-rate", "monthly_loss_pct_high")
    months = day / 30.4
    adherence = None
    if "exercise_minutes" in daily.columns and daily["exercise_minutes"].notna().any():
        ex = daily["exercise_minutes"].dropna().tail(14)
        adherence = round(float((ex >= 90).mean() * 100), 0)
    return {"model": "expected bone-density loss (projection)",
            "expected_loss_pct": [round(lo * months, 1), round(hi * months, 1)], "mission_months": round(months, 1),
            "exercise_adherence_14d_pct": adherence,
            "method": "NASA average 1-1.5% per month at weight-bearing sites x months in flight. Not a measurement: "
                      "bone density needs imaging. Exercise is the main countermeasure.",
            "evidence": ["bone-loss-rate", "bone-loss-rate-web", "vitamin-d", "urine-calcium"]}


def mass_model(daily: pd.DataFrame, k: dict) -> dict | None:
    if "body_mass" not in daily.columns:
        return None
    bm = daily[["date", "body_mass"]].dropna()
    if len(bm) < 7:
        return None
    start, now = float(bm["body_mass"].head(7).mean()), float(bm["body_mass"].tail(3).mean())
    days = (pd.Timestamp(bm["date"].iloc[-1]) - pd.Timestamp(bm["date"].iloc[0])).days
    rate = _ev_value(k, "body-mass-loss", "loss_pct_per_100_days")
    return {"model": "body-mass change vs NASA average", "change_pct": round((now - start) / start * 100, 2),
            "days": days, "nasa_average_change_pct": round(-rate * days / 100, 2), "start_kg": round(start, 1),
            "now_kg": round(now, 1), "evidence": ["body-mass-loss", "body-mass-mir"]}


def astronaut_risks(db: Session, astronaut_id: str) -> dict:
    k = load()
    if not k["available"]:
        return {"available": False, "risks": []}
    daily = astronaut_daily(db, astronaut_id)
    day = mission_day(db, astronaut_id)
    latest = latest_timestamp(db, astronaut_id)
    recent_alerts = []
    if latest is not None:
        q = (select(Alert).where((Alert.astronaut_id == astronaut_id) | Alert.astronaut_id.is_(None))
             .where(Alert.acknowledged.is_(False), Alert.observed_at >= latest - timedelta(days=3)))
        recent_alerts = list(db.execute(q).scalars())
    env_latest = latest_timestamp(db, None)
    env = load_measurements(db, None, since=env_latest - timedelta(hours=24)) if env_latest else pd.DataFrame()

    out = []
    for r in k["risks"]:
        indicators, concern, flagged, have = [], False, False, False
        for m in r["metrics"]:
            mdef = METRICS.get(m)
            if mdef is None:
                continue
            if mdef.per_astronaut:
                s = metric_summary(daily, m)
                if s["status"] != "no_data":
                    have = True
                    concern |= bool(s.get("concern"))
                indicators.append({"metric": m, "label": mdef.label, "unit": mdef.unit, "status": s["status"],
                                   "latest": s.get("latest"), "usual": s.get("baseline_median"), "concern": bool(s.get("concern"))})
            elif not env.empty and m in set(env["metric"]):
                have = True
                v = env[env["metric"] == m]["value"]
                indicators.append({"metric": m, "label": mdef.label, "unit": mdef.unit, "status": "measured",
                                   "latest": round(float(v.iloc[-1]), 2), "usual": round(float(v.mean()), 2), "concern": False})
        alerts = [{"id": a.id, "severity": a.severity, "title": a.title} for a in recent_alerts
                  if any(e.get("metric") in r["metrics"] for e in (a.evidence or []))]
        models = {}
        if r["slug"] == "risk-of-radiation-induced-cancers":
            models["radiation"] = radiation_model(db, k, day)
            flagged |= bool(models["radiation"] and models["radiation"]["above_reference"])
        if r["slug"] == "risk-of-spaceflight-induced-bone-changes":
            models["bone"] = bone_model(daily, k, day)
            b = models["bone"]
            concern |= bool(b and b["exercise_adherence_14d_pct"] is not None and b["exercise_adherence_14d_pct"] < 50)
            have = have or bool(b)
        if r["slug"] == "risk-of-inadequate-food-and-nutrition":
            models["body_mass"] = mass_model(daily, k)
        models = {kk: v for kk, v in models.items() if v}

        if r["monitoring"] == "none":
            status = "not_monitored"
        elif r["monitoring"] == "clinical":
            status = "clinical_exam"
        elif alerts or flagged:
            status = "attention"
        elif concern:
            status = "watch"     # outside this person's usual range, no alert
        elif have:
            status = "ok"
        else:
            status = "no_data"
        out.append({**{key: r[key] for key in ("slug", "name", "url", "category", "hazards", "top_risks",
                                               "what_can_be_done", "did_you_know", "formal_description", "monitoring", "note")},
                    "status": status, "indicators": indicators, "alerts": alerts, "models": models,
                    "evidence": _evidence(k, r["evidence"] + [e for m in models.values() for e in m.get("evidence", [])])})
    out.sort(key=lambda x: (STATUS_ORDER[x["status"]], x["name"]))
    counts = {s: sum(x["status"] == s for x in out) for s in STATUS_ORDER}
    return {"available": True, "astronaut_id": astronaut_id, "mission_day": day, "counts": counts, "risks": out,
            "disclaimer": "Risk status reflects the indicators this tool can measure. It is decision support, not a diagnosis."}
