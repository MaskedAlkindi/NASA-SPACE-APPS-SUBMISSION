"""Build the minimal, structured context the assistant is allowed to use.

Data minimisation: only the astronaut's callsign (never their name), daily
aggregates relevant to the question, active alerts, model outputs and a few
research passages are included. Raw time series are never sent.
"""
from __future__ import annotations

import re
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import Alert, Astronaut
from app.intelligence import models_service
from app.intelligence.daily import astronaut_daily, latest_timestamp, load_measurements
from app.intelligence.domains import environment_summary, health_summary
from app.intelligence.research import retrieve

INTENTS = {
    "cardiovascular": r"heart|hrv|pulse|cardio|blood pressure|bpm|oxygen|spo2",
    "sleep": r"sleep|tired|fatigue|rest|circadian|insomnia|nap",
    "activity": r"exercise|steps|activity|workout|training",
    "wellbeing": r"mood|stress|workload|anxious|reaction|cognitive|feel",
    "environment": r"co2|carbon|cabin|air|radiation|temperature|humidity|pressure|environment",
    "alert": r"alert|warning|caution|explain",
    "next": r"next|should i|what to do|check|recommend",
    "research": r"nasa|research|study|studies|science|evidence|osdr|inspiration4",
    "overview": r"how am i|today|overall|doing|status|summary",
}
SEVERE_SYMPTOMS = r"chest pain|faint|passed out|can'?t breathe|short(ness)? of breath|confus|severe headache|vision loss|numb"


def detect_intents(question: str) -> list[str]:
    q = question.lower()
    found = [k for k, rx in INTENTS.items() if re.search(rx, q)]
    return found or ["overview"]


def _slim_metric(m: dict) -> dict:
    keep = ("label", "unit", "latest", "latest_date", "avg_7d", "baseline_median", "baseline_range", "status", "trend_per_day_7d")
    return {k: m[k] for k in keep if k in m}


def build_context(db: Session, astronaut_id: str, question: str, max_passages: int = 3) -> dict:
    astro = db.get(Astronaut, astronaut_id)
    intents = detect_intents(question)
    daily = astronaut_daily(db, astronaut_id)
    summary = health_summary(daily)
    wanted = {"cardiovascular", "sleep", "activity", "wellbeing"}
    focus = wanted & set(intents)
    if not focus or "overview" in intents or "next" in intents or "alert" in intents:
        focus = wanted
    domains = {}
    for d in sorted(focus):
        dom = summary["domains"][d]
        domains[d] = {"status": dom["status"], "metrics": [_slim_metric(m) for m in dom["metrics"] if m["status"] != "no_data"]}
        for extra in ("sleep_timing_variability_h", "circadian_disruption", "sleep_debt_7d_h_vs_7_5h", "training_adherence_7d_pct"):
            if extra in dom:
                domains[d][extra] = dom[extra]
    latest = latest_timestamp(db, astronaut_id)
    alerts = []
    if latest is not None:
        q = (select(Alert).where((Alert.astronaut_id == astronaut_id) | (Alert.astronaut_id.is_(None)))
             .where(Alert.observed_at >= latest - timedelta(days=3)).order_by(Alert.observed_at.desc()).limit(6))
        for a in db.execute(q).scalars():
            alerts.append({"severity": a.severity, "title": a.title, "message": a.message,
                           "evidence": a.evidence[:3], "observed": a.observed_at.date().isoformat(),
                           "source": "ML model" if not a.source.startswith("rule") else "threshold rule"})
    preds = models_service.predictions(daily, history_days=7) if not daily.empty else {}
    model_out = {}
    an = (preds.get("anomaly") or {}).get("latest")
    if an and an.get("status") == "scored":
        model_out["anomaly_detection"] = {"date": an["date"], "flagged_unusual": an["is_anomaly"],
                                          "unusualness_percentile_vs_training": an["score_percentile"],
                                          "top_contributors": [{k: c[k] for k in ("label", "value", "baseline_median", "direction")}
                                                               for c in an["contributors"][:3]],
                                          "missing_inputs": an["missing"]}
    fat = preds.get("fatigue") or {}
    if fat.get("status") == "estimated":
        model_out["fatigue_estimate"] = {"value_1_to_7": fat["fatigue_estimate"], "range_80pct": fat["interval_80"],
                                         "category": fat["category"], "note": "simulation-trained model"}
    fc = []
    for s in (preds.get("forecasts") or {}).get("series", []):
        if s.get("status") == "forecast":
            fc.append({"metric": s["metric"], "trend": s["trend_direction"], "recent_7d_mean": s["recent_mean_7d"],
                       "day7_forecast": s["points"][-1]["value"],
                       "day7_range_80pct": [s["points"][-1]["lower_80"], s["points"][-1]["upper_80"]]})
    if fc:
        model_out["7_day_forecasts"] = fc
    env = None
    if "environment" in intents or any(a["title"].lower().startswith(("cabin", "elevated radiation")) for a in alerts):
        el = latest_timestamp(db, None)
        if el is not None:
            env = [{k: m[k] for k in ("label", "unit", "latest", "mean_24h", "max_24h")}
                   for m in environment_summary(load_measurements(db, None, since=el - timedelta(hours=24)))["metrics"]]
    topic_words = " ".join(a["title"] for a in alerts[:3])
    passages = retrieve(db, f"{question} {' '.join(intents)} {topic_words}", k=max_passages)
    research = [{"ref": f"R{i + 1}", "title": p["title"], "text": p["text"][:600], "type": p["evidence_type"],
                 "source": p["source_url"], "caveat": p["caveats"][:200]} for i, p in enumerate(passages)]
    # Extra grounding from the LLM workspace corpus (NASA reports + CC BY studies), when its index exists.
    try:
        from llm.rag.index import search as rag_search
        seen = {r["source"] for r in research}
        for h in rag_search(f"{question} {topic_words}", k=4):
            if len(research) >= max_passages + 2 or h.get("url") in seen or h["score"] < 0.08:
                continue
            nasa = h["source_id"].startswith("nasa")
            research.append({"ref": f"R{len(research) + 1}", "title": h["title"] + (f" (page {h['page']})" if h.get("page") else ""),
                             "text": h["text"][:600], "type": "nasa_document" if nasa else "open_access_study",
                             "source": h.get("url"),
                             "caveat": "NASA public document" if nasa else "single published study; may involve animals, cells or ground analogs"})
            seen.add(h.get("url"))
    except Exception:   # noqa: BLE001 - the corpus is optional
        pass
    data_classes = sorted(set(load_measurements(db, astronaut_id, since=latest - timedelta(days=2))["data_class"])) if latest else []
    return {
        "astronaut_callsign": astro.callsign if astro else astronaut_id,
        "as_of": summary["as_of"], "intents": intents, "data_classes_recent": data_classes,
        "observations": domains, "unavailable_metrics": [m for m in summary["unavailable_metrics"]][:12],
        "active_alerts": alerts, "model_outputs": model_out, "environment": env, "research": research,
        "severe_symptoms_mentioned": bool(re.search(SEVERE_SYMPTOMS, question.lower())),
    }
