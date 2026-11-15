"""Phone enrolment and uploads (/api/v1/devices).

Flow:
  1. The phone app generates a UUID once and shows it on screen.
  2. The phone calls POST /devices/register with that UUID and gets a device secret (shown only once to the app).
  3. An operator (mission control / flight surgeon) sees the pending phone in the Devices page and assigns it to a
     crew member.
  4. The phone uploads with headers X-Device-UUID + X-Device-Token. Data is attributed to the assigned crew member,
     never to an ID the phone chooses.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid as uuidlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import Principal, current_user, require_crew_wide
from app.database.models import Astronaut
from app.database.session import get_db
from app.devices.db_models import Device

router = APIRouter(prefix="/api/v1/devices", tags=["devices"])
PHONE_MODULES = {"ios": "apple_health", "android": "android_health"}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _out(d: Device, db: Session | None = None) -> dict:
    callsign = None
    if db is not None and d.astronaut_id:
        a = db.get(Astronaut, d.astronaut_id)
        callsign = a.callsign if a else None
    return {"device_uuid": d.device_uuid, "platform": d.platform, "model": d.model, "app_version": d.app_version,
            "label": d.label, "astronaut_id": d.astronaut_id, "callsign": callsign, "status": d.status,
            "registered_at": d.registered_at.isoformat() if d.registered_at else None,
            "last_seen": d.last_seen.isoformat() if d.last_seen else None,
            "last_upload": d.last_upload.isoformat() if d.last_upload else None, "uploads": d.uploads}


class RegisterIn(BaseModel):
    device_uuid: str
    platform: str = Field(pattern="^(ios|android|other)$")
    model: str = Field("", max_length=120)
    app_version: str = Field("", max_length=32)


def _authed_device(db: Session, device_uuid: str | None, token: str | None) -> Device:
    if not device_uuid or not token:
        raise HTTPException(401, "missing X-Device-UUID / X-Device-Token")
    d = db.get(Device, device_uuid.lower())
    if d is None or not hmac.compare_digest(d.token_hash, _hash(token)):
        raise HTTPException(401, "unknown device or wrong token")
    if d.status == "revoked":
        raise HTTPException(403, "this device was revoked by an operator")
    d.last_seen = _now()
    return d


@router.post("/register")
def register(body: RegisterIn, db: Session = Depends(get_db), x_device_token: str | None = Header(None)):
    """Called by the phone app. No user login: the phone stays 'pending' until an operator assigns it."""
    try:
        du = str(uuidlib.UUID(body.device_uuid)).lower()
    except ValueError:
        raise HTTPException(422, "device_uuid must be a UUID")
    d = db.get(Device, du)
    if d is not None:
        if x_device_token and hmac.compare_digest(d.token_hash, _hash(x_device_token)):
            d.last_seen, d.model, d.app_version = _now(), body.model or d.model, body.app_version or d.app_version
            db.commit()
            return {"device": _out(d, db), "token": None}
        if d.status != "pending":
            raise HTTPException(409, "this device ID is already enrolled; ask an operator to reset it")
        token = secrets.token_urlsafe(32)          # reinstall before assignment: issue a fresh secret
        d.token_hash, d.last_seen = _hash(token), _now()
        db.commit()
        return {"device": _out(d, db), "token": token}
    token = secrets.token_urlsafe(32)
    d = Device(device_uuid=du, platform=body.platform, model=body.model, app_version=body.app_version,
               token_hash=_hash(token), last_seen=_now())
    db.add(d)
    db.commit()
    return {"device": _out(d, db), "token": token}


@router.get("/me")
def me(db: Session = Depends(get_db), x_device_uuid: str | None = Header(None), x_device_token: str | None = Header(None)):
    d = _authed_device(db, x_device_uuid, x_device_token)
    db.commit()
    return {"device": _out(d, db)}


class UploadIn(BaseModel):
    measurements: list[dict] = Field(default_factory=list, max_length=5000)
    # Workouts in the exercise module's format (source "camera" for phone rep counting, "manual" for logs).
    workouts: list[dict] = Field(default_factory=list, max_length=200)


@router.post("/upload")
def upload(body: UploadIn, db: Session = Depends(get_db), x_device_uuid: str | None = Header(None),
           x_device_token: str | None = Header(None)):
    d = _authed_device(db, x_device_uuid, x_device_token)
    if d.status != "assigned" or not d.astronaut_id:
        db.commit()
        raise HTTPException(409, "waiting for an operator to assign this phone to a crew member")
    from app.intelligence.ingest import ingest
    from app.modules.registry import get_registry
    from app.schemas.measurement import NormalizedMeasurement
    reg = get_registry()
    mod = reg.get(PHONE_MODULES.get(d.platform, ""))
    items, errors = [], []
    for i, rec in enumerate(body.measurements):
        rec = {**rec, "astronaut_id": d.astronaut_id, "data_class": "real",
               "source_device": rec.get("source_device") or f"{d.platform} {d.model}".strip()}
        try:
            if mod is not None and ("hk_type" in rec or "record_type" in rec):
                ok, errs = mod.ingest([rec])
            else:
                ok, errs = [NormalizedMeasurement(**{"source_module": f"device_{d.platform}", **rec})], []
        except Exception as e:   # noqa: BLE001 - report per record
            ok, errs = [], [str(e).splitlines()[0]]
        items += ok
        errors += [f"record {i}: {e.split(': ', 1)[-1]}" for e in errs]
    res = ingest(db, items) if items else {"accepted": 0, "updated": 0, "alerts": []}

    workouts_saved = 0
    if body.workouts:
        from app.exercise import service as exercise
        from app.exercise.routes import SessionIn
        for i, w in enumerate(body.workouts):
            try:
                sess = SessionIn(**w)
                payload = sess.model_dump()
                payload["client_id"] = f"{d.device_uuid[:8]}-{sess.client_id}" if sess.client_id else None
                exercise.record_session(db, d.astronaut_id, payload, data_class="real")
                workouts_saved += 1
            except Exception as e:   # noqa: BLE001 - report per workout
                db.rollback()
                errors.append(f"workout {i}: {str(e).splitlines()[0][:200]}")
        d = db.get(Device, d.device_uuid)
    d.last_upload, d.uploads = _now(), (d.uploads or 0) + 1
    db.commit()
    return {"accepted": res["accepted"], "updated": res["updated"], "workouts": workouts_saved,
            "rejected": len(errors), "errors": errors[:50], "astronaut_id": d.astronaut_id}


# ---------------------------------------------------------------- operator side
@router.get("")
def list_devices(db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    rows = db.execute(select(Device).order_by(Device.registered_at.desc())).scalars().all()
    return {"devices": [_out(d, db) for d in rows]}


class AssignIn(BaseModel):
    astronaut_id: str | None = None
    label: str | None = Field(None, max_length=120)


@router.put("/{device_uuid}")
def assign(device_uuid: str, body: AssignIn, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    d = db.get(Device, device_uuid.lower())
    if d is None:
        raise HTTPException(404, "device not found")
    if body.label is not None:
        d.label = body.label
    if "astronaut_id" in body.model_fields_set:
        if body.astronaut_id:
            if db.get(Astronaut, body.astronaut_id) is None:
                raise HTTPException(422, "unknown astronaut")
            d.astronaut_id, d.status, d.assigned_by = body.astronaut_id, "assigned", user.username
        else:
            d.astronaut_id, d.status = None, "pending"
    db.commit()
    return {"device": _out(d, db)}


@router.post("/{device_uuid}/revoke")
def revoke(device_uuid: str, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    d = db.get(Device, device_uuid.lower())
    if d is None:
        raise HTTPException(404, "device not found")
    d.status, d.astronaut_id = "revoked", None
    db.commit()
    return {"device": _out(d, db)}


@router.post("/{device_uuid}/reset")
def reset(device_uuid: str, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    """Back to pending, so the phone can enrol again (e.g. after reinstalling the app)."""
    d = db.get(Device, device_uuid.lower())
    if d is None:
        raise HTTPException(404, "device not found")
    d.status, d.astronaut_id = "pending", None
    db.commit()
    return {"device": _out(d, db)}
