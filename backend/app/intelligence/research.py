"""Persist NASA research imports and provide passage retrieval (TF-IDF) for explanations."""
from __future__ import annotations

import logging
import threading

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.database.models import ResearchDataset, ResearchFinding, ResearchObservation

log = logging.getLogger("hmt.research")
_index_lock = threading.Lock()
_index: dict | None = None

TOPIC_HINTS = {"cardiovascular": "heart rate hrv blood pressure cardiac cardiovascular",
               "sleep": "sleep fatigue circadian tired rest", "environment": "co2 carbon dioxide cabin air headache",
               "radiation": "radiation dose solar particle", "wellbeing": "stress mood workload isolation cognitive reaction",
               "activity": "exercise steps activity muscle bone fitness", "research_lab": "blood lab immune inflammation inspiration4",
               "nutrition": "food nutrition body mass weight glucose insulin diet", "immune": "immune infection fever temperature virus",
               "bone": "bone density calcium fracture exercise", "vitals": "temperature glucose body mass vitals"}

RISK_TOPIC = {"risk-of-cardiovascular-adaptations": "cardiovascular", "risk-from-inadequate-sleep-and-irregular-schedules": "sleep",
              "risk-of-behavioral-conditions-and-psychiatric-disorders": "wellbeing", "risk-of-inadequate-teamwork": "wellbeing",
              "risk-of-inadequate-systems-operations-support": "wellbeing",
              "risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness": "activity",
              "risk-of-spaceflight-induced-bone-changes": "bone", "risk-of-inadequate-food-and-nutrition": "nutrition",
              "risk-of-altered-immune-system-responses": "immune", "risk-of-host-microorganism-interactions": "immune",
              "risk-of-radiation-induced-cancers": "radiation", "risk-of-hypoxia": "environment",
              "risk-of-decompression-sickness": "environment"}


def sync_hrp_findings(db: Session) -> int:
    """Load the challenge-resource knowledge (NASA HRP pages + verified report facts) into the search corpus."""
    from app.modules.nasa_hrp.module import load
    k = load()
    db.execute(delete(ResearchFinding).where(ResearchFinding.evidence_type.in_(
        ["curated_summary", "nasa_hrp_risk_page", "nasa_hrp_hazard_page", "nasa_report_fact"])))
    if not k["available"]:
        db.commit()
        invalidate_index()
        return 0
    n = 0
    for r in k["risks"]:
        summary = r["top_risks"] + (" What can be done: " + r["what_can_be_done"] if r["what_can_be_done"] else "")
        db.add(ResearchFinding(id=("hrp-" + r["slug"])[:80], topic=RISK_TOPIC.get(r["slug"], "other"), title=r["name"],
                               summary=summary[:3000], evidence_type="nasa_hrp_risk_page", source_accession=None,
                               source_url=r["url"], caveats="NASA Human Research Program page (official challenge resource).",
                               stats={"category": r["category"], "hazards": r["hazards"], "monitoring": r["monitoring"]}))
        n += 1
    for h in k["hazards"]:
        db.add(ResearchFinding(id=("hrp-" + h["slug"])[:80], topic="hazard", title=f"Hazard: {h['name']}",
                               summary=h["summary"], evidence_type="nasa_hrp_hazard_page", source_accession=None,
                               source_url=h["url"], caveats="NASA Human Research Program page (official challenge resource).", stats={}))
        n += 1
    for e in k["evidence"]:
        topic = RISK_TOPIC.get(e["risks"][0], "other") if e["risks"] else "other"
        url = e["source_url"] + (f"#page={e['page']}" if e.get("page") else "")
        where = f"{e['source']}, p. {e['page']}" if e.get("page") else e["source"]
        db.add(ResearchFinding(id=("ev-" + e["id"])[:80], topic=topic, title=e["statement"][:300],
                               summary=f"{e['statement']} Source quote: \"{e['quote']}\" ({where}).",
                               evidence_type="nasa_report_fact", source_accession=None, source_url=url,
                               caveats="Population-level finding from a NASA report; not a measurement of this astronaut.",
                               stats={"values": e.get("values", {}), "page": e.get("page"), "source": e["source"]}))
        n += 1
    db.commit()
    invalidate_index()
    return n


def save_import(db: Session, result: dict) -> dict:
    for d in result["datasets"]:
        db.merge(ResearchDataset(**d))
    db.flush()
    accs = {o["accession"] for o in result["observations"]}
    if accs:
        db.execute(delete(ResearchObservation).where(ResearchObservation.accession.in_(accs)))
        db.add_all([ResearchObservation(**{k: o[k] for k in ("accession", "source_file", "subject_id", "analyte", "value",
                                                            "unit", "range_min", "range_max", "timepoint", "phase")})
                    for o in result["observations"]])
    notable = sorted([f for f in result["findings"] if f["notable"]],
                     key=lambda f: -abs(f["mean_pct_change_R+1_vs_preflight"]))
    for f in notable[:25]:
        direction = "higher" if f["mean_pct_change_R+1_vs_preflight"] > 0 else "lower"
        db.merge(ResearchFinding(
            id=f["id"], topic="research_lab",
            title=f"Inspiration4: {f['analyte']} {direction} 1 day after return",
            summary=(f"In NASA OSDR {f['accession']} ({f['source_file']}), {f['analyte']} was on average "
                     f"{abs(f['mean_pct_change_R+1_vs_preflight']):.0f}% {direction} on R+1 than the crew's pre-flight mean, "
                     f"with {f['subjects_same_direction']} of {f['n_subjects']} crew changing in the same direction."),
            evidence_type="computed_from_dataset", source_accession=f["accession"],
            source_url=f"https://osdr.nasa.gov/bio/repo/data/studies/{f['accession']}",
            caveats="n=4 commercial astronauts, 3-day LEO mission; descriptive statistics only, no significance testing; "
                    "not transferable to an individual.", stats=f))
    db.commit()
    invalidate_index()
    return {"datasets": len(result["datasets"]), "observations": len(result["observations"]),
            "computed_findings": len(result["findings"]), "notable_findings_saved": min(25, len(notable)),
            "errors": result["errors"], "origins": result["origins"]}


_ref_cache: dict[str, tuple[float, float] | None] = {}


def lab_reference_range(analyte: str) -> tuple[float, float] | None:
    """Reference range published in the NASA OSDR lab files (e.g. GLUCOSE 65-99 mg/dL in OSD-575)."""
    if analyte in _ref_cache:
        return _ref_cache[analyte]
    from app.database.session import SessionLocal
    db = SessionLocal()
    try:
        row = db.execute(select(ResearchObservation.range_min, ResearchObservation.range_max)
                         .where(ResearchObservation.analyte == analyte, ResearchObservation.range_min.is_not(None))
                         .limit(1)).first()
    finally:
        db.close()
    rng = (float(row[0]), float(row[1])) if row and row[1] is not None else None
    if rng:
        _ref_cache[analyte] = rng
    return rng


def invalidate_index():
    global _index
    with _index_lock:
        _index = None


def _build(db: Session) -> dict:
    docs = []
    for f in db.execute(select(ResearchFinding)).scalars():
        docs.append({"id": f.id, "title": f.title, "text": f.summary, "source_url": f.source_url,
                     "evidence_type": f.evidence_type, "caveats": f.caveats, "topic": f.topic,
                     "accession": f.source_accession})
    for d in db.execute(select(ResearchDataset).where(ResearchDataset.status == "downloaded")).scalars():
        docs.append({"id": d.accession, "title": d.title, "text": d.description[:1200], "source_url": d.source_url,
                     "evidence_type": "dataset_description", "caveats": d.relevance, "topic": "research_lab",
                     "accession": d.accession})
    if not docs:
        return {"docs": [], "vec": None, "mat": None}
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    mat = vec.fit_transform([f"{d['title']} {d['text']} {TOPIC_HINTS.get(d['topic'], '')}" for d in docs])
    return {"docs": docs, "vec": vec, "mat": mat}


def retrieve(db: Session, query: str, k: int = 3) -> list[dict]:
    global _index
    with _index_lock:
        if _index is None:
            _index = _build(db)
        idx = _index
    if not idx["docs"]:
        return []
    sims = linear_kernel(idx["vec"].transform([query]), idx["mat"]).ravel()
    order = sims.argsort()[::-1][:k]
    return [{**idx["docs"][i], "score": round(float(sims[i]), 3)} for i in order if sims[i] > 0.02]
