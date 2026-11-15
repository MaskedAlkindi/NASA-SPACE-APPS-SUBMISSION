"""Exercise HTTP API (version 1, contract 1.0.0).

These routes are the stable surface for a later recommendation model. They do
not replace ``/measurements`` or ``/alerts``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Principal, current_user, require_access
from app.database.models import Astronaut
from app.database.session import get_db
from app.exercise import CONTRACT_VERSION, DISCLAIMER
from app.exercise.catalog import catalog_list
from app.exercise.inference_api import InferenceError, handle_frame, handle_landmarks, mediapipe_status
from app.exercise.programs import program_list
from app.exercise import service as exercise
from app.exercise.tracking import TRACKED_EXERCISES, public_spec

router = APIRouter(prefix="/api/v1/exercise", tags=["exercise"])


class ProfileIn(BaseModel):
    fitness_level: Literal["beginner", "intermediate", "advanced"] | None = None
    focus: Literal["balanced", "strength", "cardio", "mobility", "rehab"] | None = None
    limitations: str | None = Field(None, max_length=500)
    equipment: list[str] | None = None
    mission_phase: Literal["preflight", "in_flight", "postflight"] | None = None
    notes: str | None = Field(None, max_length=1000)


class GoalIn(BaseModel):
    period: Literal["day", "week", "month", "year"]
    metric: Literal["minutes", "sessions"]
    target: float = Field(..., gt=0, le=10000)
    label: str = Field(..., min_length=1, max_length=120)


class GoalsIn(BaseModel):
    goals: list[GoalIn] = Field(..., min_length=1, max_length=12)


class SetIn(BaseModel):
    reps: int | None = Field(None, ge=0, le=500)
    duration_s: int | None = Field(None, ge=0, le=8 * 3600)
    rest_s: int | None = Field(None, ge=0, le=3600)
    intensity: str | None = Field(None, max_length=32)


class PerformedIn(BaseModel):
    exercise_id: str = Field(..., max_length=64)
    sets: list[SetIn] = Field(default_factory=list, max_length=40)
    notes: str = Field("", max_length=500)


class SessionIn(BaseModel):
    source: Literal["manual", "camera", "imported"] = "manual"
    started_at: datetime
    ended_at: datetime | None = None
    program_id: str | None = Field(None, max_length=80)
    exercises: list[PerformedIn] = Field(..., min_length=1, max_length=30)
    perceived_exertion: int | None = Field(None, ge=1, le=10)
    heart_rate_avg: float | None = Field(None, ge=25, le=230)
    notes: str = Field("", max_length=2000)
    summary: dict[str, Any] = Field(default_factory=dict)
    client_id: str | None = Field(None, max_length=80)
    sync_health: bool = True


class InferenceIn(BaseModel):
    consent: str
    exercise_id: str
    t_ms: int | None = None
    landmarks: dict | None = None
    frames: list[dict] | None = None
    state: dict | None = None
    image_base64: str | None = None


def _astronaut(db: Session, astronaut_id: str, user: Principal) -> Astronaut:
    require_access(astronaut_id, user)
    row = db.get(Astronaut, astronaut_id)
    if row is None:
        raise HTTPException(404, "Astronaut not found")
    return row


def _data_class(user: Principal, astronaut: Astronaut) -> str:
    if not user.crew_wide:
        return "real"
    return astronaut.data_class or "real"


@router.get("/contracts")
def contracts(user: Principal = Depends(current_user)):
    """Machine-readable shapes for session, summary, recommendation, health context, and alerts."""
    return {
        "contract_version": CONTRACT_VERSION,
        "disclaimer": DISCLAIMER,
        "resources": {
            "session": "Workout session logged by camera, manual entry, or import.",
            "summary": "Rolling exercise summary for one astronaut.",
            "recommendation_request": "POST body accepted by an external model at EXERCISE_RECOMMENDER_URL.",
            "recommendation_response": "Items plus reason, source, confidence, and requires_human_review.",
            "health_context": "Read-only slice of existing daily health metrics. Not a second health database.",
            "alert_event": "Rows in the shared alerts table with category 'exercise'.",
        },
        "examples": {
            "recommendation_request": {
                "contract_version": CONTRACT_VERSION,
                "astronaut_id": "AST-001",
                "profile": {"fitness_level": "intermediate", "focus": "balanced", "limitations": "", "equipment": ["bodyweight"], "mission_phase": "in_flight"},
                "health_context": {"contract_version": CONTRACT_VERSION, "fatigue_score": 3, "sleep_duration_h": 7.2},
                "adherence_pct": 80, "weekday": 0,
            },
            "recommendation_response": {
                "contract_version": CONTRACT_VERSION, "source": "rules:exercise-recommender-1.0.0",
                "model": None, "confidence": 0.7, "requires_human_review": False, "review_reasons": [],
                "reason": "Why this example was chosen.", "items": [], "example_only": True, "disclaimer": DISCLAIMER,
            },
            "alert_event": {
                "category": "exercise", "severity": "caution", "source": "rule:exercise-review",
                "evidence": [{"metric": "heart_rate", "value": 180, "unit": "bpm"}],
            },
        },
    }


@router.get("/config")
def config(user: Principal = Depends(current_user)):
    settings = get_settings()
    return {
        "contract_version": CONTRACT_VERSION,
        "tracked_exercises": list(TRACKED_EXERCISES),
        "pose_model_url": settings.exercise_pose_model_url,
        "pose_wasm_url": settings.exercise_pose_wasm_url,
        "inference": {
            "remote_configured": bool(settings.exercise_inference_url.strip()),
            "remote_frames_enabled": bool(settings.exercise_allow_remote_frames),
            "transmits_video_by_default": False,
            "strategy": ["local", "remote", "manual"],
        },
        "recommender_configured": bool(settings.exercise_recommender_url.strip()),
        "disclaimer": DISCLAIMER,
    }


@router.get("/catalog")
def catalog(user: Principal = Depends(current_user)):
    return {"exercises": catalog_list(), "example_only": True, "disclaimer": DISCLAIMER}


@router.get("/programs")
def programs(user: Principal = Depends(current_user)):
    return {"programs": program_list(), "example_only": True, "disclaimer": DISCLAIMER}


@router.get("/tracking-spec")
def tracking_spec(user: Principal = Depends(current_user)):
    return public_spec()


@router.post("/inference/landmarks")
def inference_landmarks(body: InferenceIn, user: Principal = Depends(current_user)):
    settings = get_settings()
    payload = body.model_dump()
    if settings.exercise_inference_url.strip():
        return _forward("/v1/landmarks", payload, settings)
    try:
        return handle_landmarks(payload)
    except InferenceError as exc:
        raise HTTPException(exc.status, exc.args[0]) from None


@router.post("/inference/frame")
def inference_frame(body: InferenceIn, user: Principal = Depends(current_user)):
    settings = get_settings()
    if body.consent != "explicit_frame_upload":
        raise HTTPException(403, "Remote camera processing requires consent='explicit_frame_upload'.")
    if not settings.exercise_allow_remote_frames:
        raise HTTPException(403, "The server is not configured to accept camera frames.")
    if not settings.exercise_inference_url.strip():
        try:
            return handle_frame(body.model_dump(), allow_frames=True)
        except InferenceError as exc:
            raise HTTPException(exc.status, exc.args[0]) from None
    return _forward("/v1/frame", body.model_dump(), settings)


def _forward(path: str, payload: dict, settings) -> dict:
    url = settings.exercise_inference_url.rstrip("/") + path
    headers = {}
    if settings.exercise_inference_token:
        headers["Authorization"] = f"Bearer {settings.exercise_inference_token}"
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=5.0)
    except httpx.HTTPError as exc:
        raise HTTPException(503, "The inference service did not respond. Log the workout manually.") from exc
    if response.status_code >= 400:
        detail = response.text[:300]
        try:
            detail = response.json().get("detail", detail)
        except Exception:
            pass
        raise HTTPException(response.status_code, detail)
    return response.json()


@router.get("/runtime")
def runtime(user: Principal = Depends(current_user)):
    return {"mediapipe": mediapipe_status(), "tracked_exercises": list(TRACKED_EXERCISES)}


@router.get("/astronauts/{astronaut_id}/profile")
def get_profile(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    return exercise.profile_dict(exercise.ensure_profile(db, astronaut_id))


@router.put("/astronauts/{astronaut_id}/profile")
def put_profile(astronaut_id: str, body: ProfileIn, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    fields = body.model_dump(exclude_unset=True)
    if "equipment" in fields:
        fields["equipment"] = [str(x)[:32] for x in fields["equipment"][:12]]
    return exercise.profile_dict(exercise.save_profile(db, astronaut_id, fields))


@router.get("/astronauts/{astronaut_id}/program")
def get_program(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    assigned = exercise.active_programs(db, astronaut_id)
    return {
        "astronaut_id": astronaut_id,
        "active": assigned.get("personalized") or assigned.get("general"),
        "general": assigned.get("general"),
        "mission": assigned.get("mission"),
        "personalized": assigned.get("personalized"),
        "disclaimer": DISCLAIMER,
    }


@router.get("/astronauts/{astronaut_id}/goals")
def get_goals(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    rows = exercise.goals_for(db, astronaut_id)
    return {"astronaut_id": astronaut_id, "example_only": True,
            "goals": [{"id": g.id, "period": g.period, "metric": g.metric, "target": g.target, "label": g.label} for g in rows]}


@router.put("/astronauts/{astronaut_id}/goals")
def put_goals(astronaut_id: str, body: GoalsIn, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    rows = exercise.replace_goals(db, astronaut_id, [g.model_dump() for g in body.goals])
    return {"astronaut_id": astronaut_id, "goals": [{"id": g.id, "period": g.period, "metric": g.metric, "target": g.target, "label": g.label} for g in rows]}


@router.get("/astronauts/{astronaut_id}/sessions")
def get_sessions(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    return {"astronaut_id": astronaut_id, "contract_version": CONTRACT_VERSION,
            "sessions": [exercise.session_out(r) for r in exercise.list_sessions(db, astronaut_id)]}


@router.post("/astronauts/{astronaut_id}/sessions")
def post_session(astronaut_id: str, body: SessionIn, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    astro = _astronaut(db, astronaut_id, user)
    payload = body.model_dump()
    payload["exercises"] = [e.model_dump() if hasattr(e, "model_dump") else e for e in body.exercises]
    if not payload.get("client_id"):
        payload["client_id"] = None
    try:
        row = exercise.record_session(db, astronaut_id, payload, data_class=_data_class(user, astro))
    except KeyError as exc:
        raise HTTPException(422, f"Unknown exercise {exc.args[0]}") from None
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    return exercise.session_out(row)


@router.get("/astronauts/{astronaut_id}/progress")
def get_progress(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    return exercise.progress_report(db, astronaut_id)


@router.get("/astronauts/{astronaut_id}/calendar")
def get_calendar(astronaut_id: str, year: int, month: int, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    if not 1 <= month <= 12 or year < 2000 or year > 2100:
        raise HTTPException(422, "month and year are out of range")
    return exercise.calendar_month(db, astronaut_id, year, month)


@router.get("/astronauts/{astronaut_id}/recommendations")
def get_recommendations(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    return exercise.recommendation_for(db, astronaut_id)


@router.get("/astronauts/{astronaut_id}/health-context")
def get_health_context(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    return exercise.health_context(db, astronaut_id)


@router.get("/astronauts/{astronaut_id}/summary")
def get_summary(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    _astronaut(db, astronaut_id, user)
    return exercise.summary_for(db, astronaut_id)
