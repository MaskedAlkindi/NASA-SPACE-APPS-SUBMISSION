"""Health, auth, modules, astronauts, measurements, alerts, predictions."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.ratelimit import RateLimiter
from app.core.security import Principal, create_token, current_user, require_access, verify_passcode
from app.database.models import Alert, Astronaut, Measurement, Mission, User
from app.database.session import get_db
from app.intelligence import models_service
from app.intelligence.daily import astronaut_daily, latest_timestamp, load_measurements
from app.intelligence.domains import environment_summary, health_summary
from app.intelligence.ingest import alert_out, ingest
from app.modules.questionnaires.module import INSTRUMENTS
from app.modules.registry import get_registry
from app.schemas.measurement import IngestResult, MeasurementBatch, MeasurementOut
from app.schemas.metrics import METRICS

router = APIRouter(prefix="/api/v1")
login_limiter = RateLimiter(20, 60)


@router.get("/health", tags=["system"])
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    s = get_settings()
    models = {m["id"]: m["available"] for m in models_service.model_catalog()}
    from app.assistant.service import resolve
    try:
        pid, mdl, _ = resolve(db)
    except Exception:
        pid, mdl = "offline", None
    return {"status": "ok" if db_ok else "degraded", "database": db_ok, "models": models,
            "assistant_mode": pid, "assistant_model": mdl, "openai_model": s.openai_model if s.openai_enabled else None,
            "demo_mode": s.demo_mode, "time": datetime.now(timezone.utc).isoformat(), "version": "1.0.0", "app_name": s.app_name}


# ---------------------------------------------------------------- auth
class LoginIn(BaseModel):
    username: str = Field(..., max_length=64)
    passcode: str = Field(..., max_length=128)


@router.post("/auth/login", tags=["auth"])
def login(body: LoginIn, db: Session = Depends(get_db)):
    ok, _ = login_limiter.allow(body.username.lower())
    if not ok:
        raise HTTPException(429, "Too many login attempts")
    user = db.get(User, body.username.strip().lower())
    ok = bool(user) and verify_passcode(body.passcode, user.passcode_hash)
    if user and not ok and user.role == "mission_control":
        from app.admin.routes import check_extra_passcode
        ok = check_extra_passcode(db, body.passcode)
    if not ok:
        raise HTTPException(401, "Invalid credentials")
    return _session(user)


def _session(user: User) -> dict:
    return {"access_token": create_token(user.username, user.role, user.astronaut_id), "token_type": "bearer",
            "user": {"username": user.username, "display_name": user.display_name, "role": user.role,
                     "astronaut_id": user.astronaut_id}}


@router.post("/auth/public", tags=["auth"])
def public_session(db: Session = Depends(get_db)):
    """Open the demo with no passcode. Every visitor is mission control for this short public run."""
    user = db.get(User, "mission-control")
    if user is None:
        user = db.execute(select(User).where(User.role == "mission_control")).scalars().first()
    if user is None:
        raise HTTPException(503, "Demo account is not ready")
    return _session(user)


class SwitchIn(BaseModel):
    username: str = Field(min_length=1, max_length=64)


def _last_fetched_from_phone(db: Session, astronaut_id: str) -> str | None:
    ts = db.execute(select(func.max(Measurement.timestamp)).where(
        Measurement.astronaut_id == astronaut_id, Measurement.data_class == "real")).scalar()
    return ts.isoformat() if ts else None


@router.post("/auth/demo-switch", tags=["auth"])
def demo_switch(body: SwitchIn, db: Session = Depends(get_db)):
    """Demo only: change who you are looking as, with no passcode."""
    if not get_settings().demo_mode:
        raise HTTPException(404, "Not available")
    user = db.get(User, body.username.strip())
    if user is None:
        raise HTTPException(404, "Unknown demo user")
    return _session(user)


@router.get("/auth/demo-accounts", tags=["auth"])
def demo_accounts(db: Session = Depends(get_db)):
    s = get_settings()
    if not s.demo_mode:
        return {"demo_mode": False, "accounts": []}
    users = db.execute(select(User).order_by(User.role.desc(), User.username)).scalars()
    return {"demo_mode": True,
            "accounts": [{"username": u.username, "display_name": u.display_name, "role": u.role,
                          "astronaut_id": u.astronaut_id} for u in users]}


@router.get("/auth/me", tags=["auth"])
def me(user: Principal = Depends(current_user)):
    return {"username": user.username, "role": user.role, "astronaut_id": user.astronaut_id}


# ---------------------------------------------------------------- modules
@router.get("/modules", tags=["modules"])
def modules(db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    rows = db.execute(select(Measurement.source_module, func.count(Measurement.id), func.max(Measurement.timestamp))
                      .group_by(Measurement.source_module)).all()
    stats = {r[0]: {"count": int(r[1]), "last_timestamp": r[2].isoformat() if r[2] else None} for r in rows}
    return {"modules": get_registry().describe_all(stats), "metrics": [vars(m) for m in METRICS.values()]}


@router.get("/questionnaires", tags=["modules"])
def questionnaires(user: Principal = Depends(current_user)):
    return {"instruments": INSTRUMENTS}


# ---------------------------------------------------------------- mission / astronauts
@router.get("/mission", tags=["astronauts"])
def mission(db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    m = db.execute(select(Mission)).scalars().first()
    if not m:
        raise HTTPException(404, "No mission configured")
    latest = latest_timestamp(db, None) or datetime.now(timezone.utc)
    day = (latest.date() - m.start_date).days + 1
    crew = db.execute(select(Astronaut).where(Astronaut.mission_id == m.id)).scalars().all()
    q = select(Alert).where(Alert.acknowledged.is_(False)).order_by(Alert.observed_at.desc()).limit(50)
    visible = [a for a in db.execute(q).scalars() if a.astronaut_id is None or user.can_access(a.astronaut_id)]
    return {"id": m.id, "name": m.name, "description": m.description, "vehicle": m.vehicle, "data_class": m.data_class,
            "start_date": m.start_date.isoformat(), "planned_duration_days": m.planned_duration_days, "mission_day": day,
            "crew_count": len(crew), "visible_crew": [c.id for c in crew if user.can_access(c.id)],
            "active_alerts": [alert_out(a) for a in visible[:20]],
            "alert_counts": {s: sum(a.severity == s for a in visible) for s in ("warning", "caution", "info")},
            "sim_running": bool(get_registry().get("simulation") and get_registry().get("simulation").state.get("running"))}


@router.get("/astronauts", tags=["astronauts"])
def astronauts(db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    out = []
    for a in db.execute(select(Astronaut).order_by(Astronaut.id)).scalars():
        if not user.can_access(a.id):
            continue
        daily = astronaut_daily(db, a.id, days=40)
        summ = health_summary(daily)
        n_alerts = db.execute(select(func.count(Alert.id)).where(Alert.astronaut_id == a.id, Alert.acknowledged.is_(False),
                                                                 Alert.severity != "info")).scalar()
        key = {}
        for dom in summ["domains"].values():
            for m in dom["metrics"]:
                if m["metric"] in ("resting_heart_rate", "hrv_sdnn", "sleep_duration", "steps", "fatigue_score") and m["status"] != "no_data":
                    key[m["metric"]] = {"latest": m["latest"], "status": m["status"], "unit": m["unit"]}
        out.append({"id": a.id, "callsign": a.callsign, "name": a.name, "role": a.role, "data_class": a.data_class,
                    "as_of": summ["as_of"], "last_fetched_from_phone": _last_fetched_from_phone(db, a.id) if a.data_class == "real" else None,
                    "key_metrics": key, "open_alerts": n_alerts,
                    "domain_status": {k: v["status"] for k, v in summ["domains"].items()}})
    return {"astronauts": out}


@router.get("/astronauts/{astronaut_id}/summary", tags=["astronauts"])
def astronaut_summary(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    require_access(astronaut_id, user)
    a = db.get(Astronaut, astronaut_id)
    if not a:
        raise HTTPException(404, "Astronaut not found")
    return {"astronaut": {"id": a.id, "callsign": a.callsign, "name": a.name, "role": a.role, "data_class": a.data_class},
            "last_fetched_from_phone": _last_fetched_from_phone(db, astronaut_id) if a.data_class == "real" else None,
            **health_summary(astronaut_daily(db, astronaut_id))}


@router.get("/astronauts/{astronaut_id}/measurements", tags=["measurements"], response_model=dict)
def astronaut_measurements(astronaut_id: str, metric: list[str] | None = Query(None), days: int = Query(14, ge=1, le=365),
                           resolution: Literal["raw", "daily"] = "raw", limit: int = Query(5000, ge=1, le=20000),
                           db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    require_access(astronaut_id, user)
    if not db.get(Astronaut, astronaut_id):
        raise HTTPException(404, "Astronaut not found")
    for m in metric or []:
        if m not in METRICS:
            raise HTTPException(422, f"unknown metric {m}")
    latest = latest_timestamp(db, astronaut_id)
    if latest is None:
        return {"astronaut_id": astronaut_id, "resolution": resolution, "items": []}
    since = latest - timedelta(days=days)
    if resolution == "daily":
        from app.intelligence.daily import daily_frame
        df = daily_frame(load_measurements(db, astronaut_id, since=since))
        cols = [c for c in df.columns if c != "date" and (not metric or c in metric)]
        items = [{"date": str(r["date"].date()), **{c: (None if r[c] != r[c] else round(float(r[c]), 2)) for c in cols}}
                 for _, r in df.iterrows()]
        return {"astronaut_id": astronaut_id, "resolution": "daily", "metrics": cols, "items": items}
    q = select(Measurement).where(Measurement.astronaut_id == astronaut_id, Measurement.timestamp >= since)
    if metric:
        q = q.where(Measurement.metric.in_(metric))
    rows = db.execute(q.order_by(Measurement.timestamp.desc()).limit(limit)).scalars().all()
    return {"astronaut_id": astronaut_id, "resolution": "raw",
            "items": [MeasurementOut.model_validate(r).model_dump(mode="json") for r in reversed(rows)]}


@router.get("/environment", tags=["measurements"])
def environment(hours: int = Query(48, ge=1, le=24 * 60), db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    latest = latest_timestamp(db, None)
    if latest is None:
        return {"summary": {"status": "no_data", "metrics": []}, "series": []}
    raw = load_measurements(db, None, since=latest - timedelta(hours=hours))
    series = {}
    for r in raw.itertuples():
        series.setdefault(r.timestamp.isoformat(), {"timestamp": r.timestamp.isoformat()})[r.metric] = r.value
    return {"summary": environment_summary(raw), "series": list(series.values())}


@router.post("/measurements", tags=["measurements"], response_model=IngestResult)
def post_measurements(batch: MeasurementBatch, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    reg = get_registry()
    module_id = batch.module or "generic"
    if batch.module:
        mod = reg.get(batch.module)
        if mod is None or not mod.accepts_ingest:
            raise HTTPException(422, f"module '{batch.module}' unavailable or does not accept ingestion")
        mods = [mod]
    else:
        mods = None
    errors, items = [], []
    for i, rec in enumerate(batch.measurements):
        aid = rec.get("astronaut_id")
        metric = rec.get("metric")
        is_env = metric in METRICS and not METRICS[metric].per_astronaut
        if is_env and not user.crew_wide:
            errors.append(f"record {i}: environment data requires mission_control role")
            continue
        if not is_env:
            if aid is None and user.astronaut_id:
                aid = user.astronaut_id
                rec = {**rec, "astronaut_id": aid}
            if not user.can_access(aid):
                errors.append(f"record {i}: not allowed for astronaut {aid}")
                continue
        if rec.get("data_class") == "simulated" and not user.crew_wide:
            errors.append(f"record {i}: only crew-wide roles may submit simulated data")
            continue
        if mods:
            ok, errs = mods[0].ingest([rec])
        else:
            target = reg.get("environment") if is_env else None
            if target is None:
                from app.schemas.measurement import NormalizedMeasurement
                try:
                    ok, errs = [NormalizedMeasurement(**{"source_module": "api", **rec})], []
                except Exception as e:
                    ok, errs = [], [str(e).splitlines()[0]]
            else:
                ok, errs = target.ingest([rec])
        items += ok
        errors += [f"record {i}: {e.split(': ', 1)[-1]}" for e in errs]
    res = ingest(db, items) if items else {"accepted": 0, "updated": 0, "alerts": []}
    return IngestResult(accepted=res["accepted"], updated=res["updated"], rejected=len(errors), errors=errors[:50],
                        alerts_raised=len(res["alerts"]))


# ---------------------------------------------------------------- alerts & predictions
@router.get("/astronauts/{astronaut_id}/alerts", tags=["intelligence"])
def astronaut_alerts(astronaut_id: str, include_environment: bool = True, include_acknowledged: bool = False,
                     limit: int = Query(50, le=500), db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    require_access(astronaut_id, user)
    cond = (Alert.astronaut_id == astronaut_id)
    if include_environment:
        cond = cond | Alert.astronaut_id.is_(None)
    q = select(Alert).where(cond)
    if not include_acknowledged:
        q = q.where(Alert.acknowledged.is_(False))
    rows = db.execute(q.order_by(Alert.observed_at.desc(), Alert.id.desc()).limit(limit)).scalars()
    return {"astronaut_id": astronaut_id, "alerts": [alert_out(a) for a in rows]}


@router.post("/alerts/{alert_id}/acknowledge", tags=["intelligence"])
def acknowledge(alert_id: int, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    a = db.get(Alert, alert_id)
    if not a or (a.astronaut_id and not user.can_access(a.astronaut_id)) or (a.astronaut_id is None and not user.crew_wide):
        raise HTTPException(404, "Alert not found")
    a.acknowledged = True
    db.commit()
    return alert_out(a)


@router.get("/astronauts/{astronaut_id}/predictions", tags=["intelligence"])
def astronaut_predictions(astronaut_id: str, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    require_access(astronaut_id, user)
    if not db.get(Astronaut, astronaut_id):
        raise HTTPException(404, "Astronaut not found")
    daily = astronaut_daily(db, astronaut_id)
    return {"astronaut_id": astronaut_id, "as_of": str(daily["date"].max().date()) if not daily.empty else None,
            "disclaimer": "Model outputs are estimates from prototype models trained on simulated data. Not a diagnosis.",
            **models_service.predictions(daily)}


@router.get("/models", tags=["intelligence"])
def models(user: Principal = Depends(current_user)):
    return {"models": models_service.model_catalog()}
