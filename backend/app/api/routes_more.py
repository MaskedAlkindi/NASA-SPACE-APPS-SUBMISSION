"""Assistant, research, simulation and live WebSocket endpoints."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assistant import jobs as chat_jobs
from app.assistant import service as assistant
from app.core.config import get_settings
from app.core.events import broadcaster
from app.core.security import Principal, current_user, decode_token, require_access, require_crew_wide
from app.database.models import Astronaut, ResearchDataset, ResearchFinding, ResearchObservation
from app.database.seed import seed_history
from app.database.session import SessionLocal, get_db
from app.intelligence.daily import latest_timestamp
from app.intelligence.ingest import ingest
from app.intelligence.research import retrieve, save_import
from app.modules.registry import get_registry
from ml.datasets.synthetic import DEFAULT_CREW, SCENARIOS

log = logging.getLogger("hmt.api")
router = APIRouter(prefix="/api/v1")


# ---------------------------------------------------------------- assistant
class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=4000)


class ChatIn(BaseModel):
    astronaut_id: str | None = Field(None, max_length=32)
    message: str = Field(..., min_length=1, max_length=1000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    provider: str | None = Field(None, pattern="^(default|auto|openai|ollama|offline)$",
                                 description="Override the saved default for this request")
    model: str | None = Field(None, max_length=120)
    job_id: str | None = Field(None, max_length=64)


def _checked_astronaut(body: ChatIn, db: Session, user: Principal) -> str:
    aid = body.astronaut_id or user.astronaut_id
    if not aid:
        raise HTTPException(422, "astronaut_id is required for crew-wide accounts")
    require_access(aid, user)
    if not db.get(Astronaut, aid):
        raise HTTPException(404, "Astronaut not found")
    if body.provider not in (None, "default"):
        try:
            assistant.validate_choice(body.provider, body.model)
        except ValueError as e:
            raise HTTPException(422, str(e))
    return aid


@router.post("/assistant/chat", tags=["assistant"])
def chat(body: ChatIn, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    aid = _checked_astronaut(body, db, user)
    return assistant.chat(db, user.username, aid, body.message, [h.model_dump() for h in body.history],
                          body.provider, body.model)


@router.post("/assistant/chat/jobs", tags=["assistant"])
def start_chat_job(body: ChatIn, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    """Start the answer on the server and return at once. The page polls the job."""
    aid = _checked_astronaut(body, db, user)
    job_id = chat_jobs.start_chat_job(
        user.username, aid, body.message, [h.model_dump() for h in body.history],
        body.provider, body.model, body.job_id,
    )
    return {"id": job_id, "status": "pending"}


@router.get("/assistant/chat/jobs/{job_id}", tags=["assistant"])
def read_chat_job(job_id: str, user: Principal = Depends(current_user)):
    job = chat_jobs.get_job(job_id, user.username)
    if job is None:
        raise HTTPException(404, "Chat job not found")
    if job["status"] == "done":
        return {"id": job_id, "status": "done", **job["result"]}
    if job["status"] == "error":
        return {"id": job_id, "status": "error", "detail": job["error"]}
    return {"id": job_id, "status": "pending"}


@router.get("/assistant/status", tags=["assistant"])
def assistant_status(db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    s = get_settings()
    st = assistant.status(db)
    return {**st, "mode": st["active"]["provider"], "model": st["active"]["model"],
            "max_output_tokens": s.openai_max_output_tokens, "history_limit": s.assistant_history_limit,
            "rate_limit_per_minute": s.assistant_rate_limit_per_minute,
            "daily_budget": {"requests": s.assistant_daily_request_budget, "tokens": s.assistant_daily_token_budget},
            "usage_today": assistant.usage_today(db)}


class AssistantSettingsIn(BaseModel):
    provider: str = Field(..., pattern="^(auto|openai|ollama|offline)$")
    model: str | None = Field(None, max_length=120)


@router.put("/assistant/settings", tags=["assistant"])
def assistant_settings(body: AssistantSettingsIn, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    """Save the default provider/model for everyone (mission control / flight surgeon only)."""
    try:
        assistant.save_default(db, body.provider, body.model, user.username)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return assistant.status(db)


# ---------------------------------------------------------------- research
@router.get("/research/datasets", tags=["research"])
def datasets(status: str | None = None, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    q = select(ResearchDataset)
    if status:
        q = q.where(ResearchDataset.status == status)
    rows = db.execute(q.order_by(ResearchDataset.status, ResearchDataset.accession)).scalars().all()
    counts = dict(db.execute(select(ResearchObservation.accession, func.count(ResearchObservation.id))
                             .group_by(ResearchObservation.accession)).all())
    mod = get_registry().get("nasa_osdr")
    return {"module_status": mod.status() if mod else {"state": "unavailable"},
            "datasets": [{"accession": d.accession, "title": d.title, "description": d.description[:1500],
                          "organism": d.organism, "mission": d.mission, "project_type": d.project_type,
                          "assay_types": d.assay_types, "release_date": d.release_date, "source_url": d.source_url,
                          "license": d.license, "doi": d.doi, "citation": d.citation, "relevance": d.relevance,
                          "status": d.status, "observations": int(counts.get(d.accession, 0)),
                          "files": d.files[:40], "extra": d.extra,
                          "retrieved_at": d.retrieved_at.isoformat() if d.retrieved_at else None} for d in rows]}


@router.get("/research/findings", tags=["research"])
def findings(topic: str | None = None, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    q = select(ResearchFinding)
    if topic:
        q = q.where(ResearchFinding.topic == topic)
    return {"findings": [{"id": f.id, "topic": f.topic, "title": f.title, "summary": f.summary, "evidence_type": f.evidence_type,
                          "source_accession": f.source_accession, "source_url": f.source_url, "caveats": f.caveats,
                          "stats": f.stats} for f in db.execute(q.order_by(ResearchFinding.evidence_type, ResearchFinding.id)).scalars()]}


@router.get("/research/datasets/{accession}/observations", tags=["research"])
def observations(accession: str, analyte: str | None = None, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    q = select(ResearchObservation).where(ResearchObservation.accession == accession)
    if analyte:
        q = q.where(ResearchObservation.analyte == analyte)
    rows = db.execute(q.limit(5000)).scalars().all()
    analytes = sorted(set(db.execute(select(ResearchObservation.analyte).where(
        ResearchObservation.accession == accession).distinct()).scalars())) if not analyte else [analyte]
    return {"accession": accession, "analytes": analytes, "data_class": "research",
            "items": [{"subject_id": r.subject_id, "analyte": r.analyte, "value": r.value, "unit": r.unit,
                       "range_min": r.range_min, "range_max": r.range_max, "timepoint": r.timepoint, "phase": r.phase,
                       "source_file": r.source_file} for r in rows]}


@router.get("/research/search", tags=["research"])
def research_search(q: str = Query(..., min_length=2, max_length=200), db: Session = Depends(get_db),
                    user: Principal = Depends(current_user)):
    return {"query": q, "passages": retrieve(db, q, k=5)}


def run_nasa_import(refresh: bool = False) -> dict:
    mod = get_registry().get("nasa_osdr")
    if mod is None:
        return {"error": "nasa_osdr module unavailable"}
    result = mod.run_import(refresh=refresh)
    db = SessionLocal()
    try:
        return save_import(db, result)
    except Exception as e:
        db.rollback()
        mod.last_import["errors"].append(f"saving import failed: {type(e).__name__}")
        raise
    finally:
        db.close()


@router.post("/research/import", tags=["research"])
async def research_import(refresh: bool = False, user: Principal = Depends(require_crew_wide)):
    return await run_in_threadpool(run_nasa_import, refresh)


# ---------------------------------------------------------------- challenge resources (NASA HRP)
@router.get("/challenge", tags=["research"])
def challenge(user: Principal = Depends(current_user)):
    """The official challenge Resources: provenance, hazards, risks, verified evidence and indicator coverage."""
    from app.modules.nasa_hrp.module import load
    from app.modules.nasa_hrp.sources import CHALLENGE_INDICATORS, RESOURCES_TAB
    from app.schemas.metrics import METRICS
    k = load()
    if not k["available"]:
        raise HTTPException(503, "challenge snapshot missing")
    m = k["manifest"]
    coverage = [{"indicator": ind, "metrics": [{"metric": x, "label": METRICS[x].label, "unit": METRICS[x].unit}
                                                for x in mets if x in METRICS], "supported": all(x in METRICS for x in mets)}
                for ind, mets in CHALLENGE_INDICATORS.items()]
    return {"resources_tab": RESOURCES_TAB, "generated_at": m["generated_at"], "resources": m["resources"],
            "subpages": [{k2: d.get(k2) for k2 in ("slug", "url", "title", "status", "bytes", "sha256", "linked_documents")}
                         for d in m["subpages"]],
            "documents": m["documents"], "datasets": m["datasets"], "datasets_note": m["datasets_note"],
            "hazards": k["hazards"], "risks": [{key: r[key] for key in ("slug", "name", "url", "category", "hazards",
                                                                          "monitoring", "metrics", "note", "evidence")}
                                               for r in k["risks"]],
            "evidence": k["evidence"], "indicator_coverage": coverage}


@router.get("/astronauts/{astronaut_id}/risks", tags=["intelligence"])
def astronaut_risk_view(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    require_access(astronaut_id, user)
    if not db.get(Astronaut, astronaut_id):
        raise HTTPException(404, "Astronaut not found")
    from app.intelligence.risks import astronaut_risks
    return astronaut_risks(db, astronaut_id)


# ---------------------------------------------------------------- simulation
class SimStart(BaseModel):
    scenario: str = Field("cardio_anomaly")
    astronaut_id: str | None = Field(None, max_length=32)
    days: int = Field(4, ge=1, le=30)
    severity: float = Field(1.0, ge=0.2, le=2.0)
    tick_seconds: float | None = Field(None, ge=0.05, le=30)


async def _sim_sink(records: list[dict]):
    sim = get_registry().get("simulation")

    def work():
        items, errors = sim.ingest(records)
        if errors:
            log.warning("sim records rejected: %s", errors[:2])
        db = SessionLocal()
        try:
            ingest(db, items)
        finally:
            db.close()
        day_end = {r["astronaut_id"] for r in records if r.get("astronaut_id") and r.get("metric") == "exercise_minutes"}
        if day_end:
            from app.ai_engine.service import schedule_now
            schedule_now(sorted(day_end))
    await run_in_threadpool(work)


@router.get("/simulation/scenarios", tags=["simulation"])
def scenarios(user: Principal = Depends(current_user)):
    return {"scenarios": [{"id": k, "description": v} for k, v in SCENARIOS.items()],
            "crew": [{"id": p.astronaut_id, "callsign": p.callsign} for p in DEFAULT_CREW]}


def _future_sim_data(db: Session) -> bool:
    """Simulated readings dated after the real clock = a simulation has not been discarded yet."""
    from app.database.models import Measurement
    soon = datetime.now(timezone.utc) + timedelta(minutes=10)
    return db.execute(select(Measurement.id).where(Measurement.timestamp > soon, Measurement.data_class == "simulated").limit(1)).first() is not None


@router.get("/simulation/status", tags=["simulation"])
def sim_status(db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    sim = get_registry().get("simulation")
    state = dict(sim.state) if sim else {"running": False, "error": "simulation module unavailable"}
    state["server_time"] = datetime.now(timezone.utc).isoformat()
    state["discardable"] = bool(state.get("running") or state.get("start_at")) or _future_sim_data(db)
    return state


@router.post("/simulation/discard", tags=["simulation"])
def sim_discard(db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    """Undo a simulation run: remove its readings, alerts and model results, and return to the real date and time."""
    from sqlalchemy import delete
    from app.ai_engine.db_models import AiAssessment
    from app.database.models import Alert, Measurement
    sim = get_registry().get("simulation")
    state = dict(sim.state) if sim else {}
    if sim:
        sim.stop()
    now = datetime.now(timezone.utc)
    cutoff = datetime.fromisoformat(state["start_at"]) if state.get("start_at") else now
    cutoff = min(cutoff, now)
    wall = datetime.fromisoformat(state["started_wall"]) if state.get("started_wall") else None
    m = db.execute(delete(Measurement).where(Measurement.timestamp > cutoff, Measurement.data_class == "simulated")).rowcount
    a = db.execute(delete(Alert).where(Alert.data_class == "simulated", Alert.observed_at > cutoff)).rowcount
    if wall is not None:
        a += db.execute(delete(Alert).where(Alert.data_class == "simulated", Alert.created_at >= wall)).rowcount
    crew = [p.astronaut_id for p in DEFAULT_CREW]
    q = delete(AiAssessment).where(AiAssessment.astronaut_id.in_(crew))
    r = db.execute(q.where(AiAssessment.assessed_at >= wall) if wall is not None else q.where(AiAssessment.assessed_at >= now - timedelta(days=1))).rowcount
    db.commit()
    if sim:
        sim.state = {"running": False}
    from app.ai_engine.service import schedule_now
    schedule_now(crew)    # model results return to the real data
    broadcaster.publish({"type": "simulation", "state": {"running": False, "discarded": True}})
    return {"discarded": True, "measurements": m, "alerts": a, "assessments": r, "time": now.isoformat()}


@router.post("/simulation/start", tags=["simulation"])
async def sim_start(body: SimStart, user: Principal = Depends(require_crew_wide)):
    sim = get_registry().get("simulation")
    if sim is None:
        raise HTTPException(503, "simulation module unavailable")
    if body.scenario not in SCENARIOS:
        raise HTTPException(422, f"unknown scenario; choose from {list(SCENARIOS)}")
    if body.astronaut_id and body.astronaut_id not in {p.astronaut_id for p in DEFAULT_CREW}:
        raise HTTPException(422, "astronaut_id must be a simulated crew member")

    def last_ts():
        db = SessionLocal()
        try:
            return latest_timestamp(db, None) or latest_timestamp(db, DEFAULT_CREW[0].astronaut_id)
        finally:
            db.close()
    start_at = await run_in_threadpool(last_ts) or datetime.now(timezone.utc)
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=timezone.utc)
    state = sim.start(_sim_sink, start_at, body.scenario, body.astronaut_id, body.days, body.severity,
                      body.tick_seconds or get_settings().sim_tick_seconds)
    broadcaster.publish({"type": "simulation", "state": state})
    return state


@router.post("/simulation/stop", tags=["simulation"])
def sim_stop(user: Principal = Depends(require_crew_wide)):
    sim = get_registry().get("simulation")
    if sim is None:
        raise HTTPException(503, "simulation module unavailable")
    state = sim.stop()
    broadcaster.publish({"type": "simulation", "state": state})
    return state


@router.post("/simulation/reset", tags=["simulation"])
def sim_reset(db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    sim = get_registry().get("simulation")
    if sim:
        sim.stop()
    n = seed_history(db, force=True)
    return {"reseeded_measurements": n}


# ---------------------------------------------------------------- live updates
@router.websocket("/ws/live")
async def live(ws: WebSocket):
    """Send {"token": "..."} as the first message; then receive measurement/alert events."""
    await ws.accept()
    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=10)
    except Exception:
        await ws.close(code=4401)
        return
    user = decode_token(str(first.get("token", ""))) if isinstance(first, dict) else None
    if user is None:
        await ws.send_json({"type": "error", "detail": "unauthorised"})
        await ws.close(code=4401)
        return
    q = broadcaster.subscribe()
    await ws.send_json({"type": "hello", "user": user.username})
    try:
        while True:
            ev = await q.get()
            if ev["type"] == "measurements":
                items = [i for i in ev["items"] if i["astronaut_id"] is None or user.can_access(i["astronaut_id"])]
                if not items:
                    continue
                ev = {"type": "measurements", "items": items}
            elif ev["type"] == "alert":
                aid = ev["alert"]["astronaut_id"]
                if aid is not None and not user.can_access(aid):
                    continue
            await ws.send_json(ev)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        broadcaster.unsubscribe(q)
