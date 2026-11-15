"""AI engine API (/api/v1/ai). See docs/ai/API.md."""
from __future__ import annotations

import json
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.adapters.exercise import CONTRACTS_DIR, ExerciseGuidanceV1, ExerciseSessionSummaryV1, recommend
from ai.imported.store import SAMPLE, delete_set, is_imported, normalize, save_set
from ai.core.types import Assessment
from app.ai_engine import service
from app.ai_engine.data_view import BackendHealthDataView
from app.ai_engine.db_models import AiExerciseSession
from app.core.security import Principal, current_user, require_access, require_crew_wide
from app.database.models import Alert, Astronaut
from app.database.session import get_db
from app.intelligence.ingest import alert_out

router = APIRouter(prefix="/api/v1/ai", tags=["ai engine"])


def _summary(d: dict) -> dict:
    rep = d.get("report") or {}
    return {k: d[k] for k in ("id", "name", "version", "category", "description", "intended_use", "not_intended_for",
                              "evidence_level", "validated_on_astronauts", "status", "enabled", "thresholds",
                              "supported_indicators", "datasets", "inputs", "outputs", "execution", "alerting", "health", "load_error",
                              "imported", "rules")} | {
        "has_report": bool(rep), "report": rep}


@router.get("/models")
def list_models(user: Principal = Depends(current_user)):
    reg = service.registry()
    return {"engine_enabled": service.ENABLED, "models": [_summary(d) for d in reg.describe_all()],
            "invalid_manifests": reg.invalid}


@router.get("/models/sample")
def sample_model(user: Principal = Depends(current_user)):
    """The fatigue build-up set. The same file is also at /models/fatigue-buildup.health01.json."""
    return SAMPLE


@router.post("/models/import")
def import_model(body: dict, user: Principal = Depends(require_crew_wide)):
    """Install a model set and attach it to alerts. The file cannot contain code."""
    try:
        spec = normalize(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    reg = service.registry()
    existing = reg.entries.get(spec["id"])
    if existing is not None and not is_imported(existing.folder):
        raise HTTPException(409, "that id is already a built-in model")
    try:
        save_set(body)
    except (ValueError, OSError) as exc:
        raise HTTPException(422, str(exc)) from exc
    reg.discover()
    if spec["id"] not in reg.entries:
        delete_set(spec["id"])
        reg.discover()
        reason = next((msg for path, msg in reg.invalid.items() if spec["id"] in path), "the model file could not be loaded")
        raise HTTPException(422, reason)
    return _summary(reg.describe(spec["id"]))


@router.delete("/models/{model_id}")
def remove_imported_model(model_id: str, user: Principal = Depends(require_crew_wide)):
    reg = service.registry()
    entry = reg.entries.get(model_id)
    if entry is None or not is_imported(entry.folder):
        raise HTTPException(404, "Imported model not found")
    reg.unload(model_id)
    delete_set(model_id)
    reg.discover()
    return {"deleted": model_id}


@router.get("/models/{model_id}")
def get_model(model_id: str, user: Principal = Depends(current_user)):
    reg = service.registry()
    if model_id not in reg.entries:
        raise HTTPException(404, "Model not found")
    return _summary(reg.describe(model_id))


class ModelUpdate(BaseModel):
    enabled: bool | None = None
    thresholds: dict[str, float] | None = None


@router.put("/models/{model_id}")
def update_model(model_id: str, body: ModelUpdate, user: Principal = Depends(require_crew_wide)):
    reg = service.registry()
    if model_id not in reg.entries:
        raise HTTPException(404, "Model not found")
    known = set(reg.entries[model_id].manifest.alerting.thresholds)
    if body.thresholds and not set(body.thresholds) <= known:
        raise HTTPException(422, f"unknown thresholds; allowed: {sorted(known)}")
    st = reg.state.get(model_id) or {}
    if body.enabled is not None:
        st["enabled"] = body.enabled
    if body.thresholds:
        st["thresholds"] = {**st.get("thresholds", {}), **body.thresholds}
    reg.state.set(model_id, st)
    if body.enabled is False:
        reg.unload(model_id)
    return _summary(reg.describe(model_id))


def _check(db: Session, user: Principal, astronaut_id: str):
    require_access(astronaut_id, user)
    if not db.get(Astronaut, astronaut_id):
        raise HTTPException(404, "Astronaut not found")


@router.post("/astronauts/{astronaut_id}/run")
async def run_models(astronaut_id: str, model_id: list[str] | None = Query(None), db: Session = Depends(get_db),
                     user: Principal = Depends(current_user)):
    _check(db, user, astronaut_id)
    res, alerts = await run_in_threadpool(service.run_for, db, astronaut_id, model_id)
    return {"astronaut_id": astronaut_id, "assessments": [a.model_dump(mode="json") for a in res],
            "alerts_created": [alert_out(a) for a in alerts]}


@router.get("/astronauts/{astronaut_id}/assessments")
async def assessments(astronaut_id: str, refresh: bool = False, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _check(db, user, astronaut_id)
    rows = service.latest(db, astronaut_id)
    if refresh or not rows:
        await run_in_threadpool(service.run_for, db, astronaut_id)
        rows = service.latest(db, astronaut_id)
    return {"astronaut_id": astronaut_id, "assessments": rows,
            "note": "Research and simulation models; not diagnoses. Evidence level is stated per assessment."}


@router.get("/astronauts/{astronaut_id}/exercise-guidance", response_model=ExerciseGuidanceV1)
async def exercise_guidance(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    """Contract exercise_guidance.v1 for the exercise module (conservative; may abstain)."""
    _check(db, user, astronaut_id)
    rows = service.latest(db, astronaut_id)
    if not rows:
        await run_in_threadpool(service.run_for, db, astronaut_id)
        rows = service.latest(db, astronaut_id)
    assess = [Assessment(**r) for r in rows]
    view = BackendHealthDataView(db, astronaut_id)
    since = view._now_anchor() - timedelta(days=3)
    al = [alert_out(a) for a in db.execute(select(Alert).where(
        (Alert.astronaut_id == astronaut_id), Alert.acknowledged.is_(False), Alert.observed_at >= since)).scalars()]
    ex = view.daily(["exercise_minutes"], days=14)["exercise_minutes"].tolist()
    return recommend(astronaut_id, assess, al, view.exercise_sessions(14), ex)


class SessionBatch(BaseModel):
    sessions: list[ExerciseSessionSummaryV1] = Field(..., max_length=500)


@router.post("/exercise/session-summaries")
def post_sessions(body: SessionBatch, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    """Contract exercise_session_summary.v1: the exercise module reports sessions to the AI engine."""
    accepted, updated = 0, 0
    for s in body.sessions:
        require_access(s.astronaut_id, user)
        if s.data_class == "simulated" and not user.crew_wide:
            raise HTTPException(403, "only crew-wide roles may submit simulated sessions")
        row = db.execute(select(AiExerciseSession).where(AiExerciseSession.astronaut_id == s.astronaut_id,
                                                         AiExerciseSession.session_id == s.session_id)).scalar_one_or_none()
        payload = s.model_dump(mode="json")
        if row:
            row.payload, row.started_at, row.planned = payload, s.started_at, s.planned
            updated += 1
        else:
            db.add(AiExerciseSession(astronaut_id=s.astronaut_id, session_id=s.session_id, started_at=s.started_at,
                                     payload=payload, planned=s.planned))
            accepted += 1
    db.commit()
    return {"accepted": accepted, "updated": updated, "contract": "exercise_session_summary.v1"}


@router.get("/contracts")
def contracts(user: Principal = Depends(current_user)):
    out = {}
    for p in sorted(CONTRACTS_DIR.glob("*.json")):
        out[p.stem] = json.loads(p.read_text(encoding="utf-8"))
    return {"contracts": out}
