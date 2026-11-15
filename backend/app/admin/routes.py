"""Mission Control is the admin: extra sign-in passcodes and crew management (/api/v1/admin)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.admin.db_models import ExtraPasscode
from app.core.security import Principal, current_user, hash_passcode, verify_passcode
from app.database.models import Alert, Astronaut, Measurement, User, utcnow
from app.database.session import get_db

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
ADMIN_ROLE = "mission_control"


def require_admin(user: Principal = Depends(current_user)) -> Principal:
    if user.role != ADMIN_ROLE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Mission Control (admin) only")
    return user


def check_extra_passcode(db: Session, passcode: str) -> bool:
    """True if the passcode matches one of the extra Mission Control passcodes (and records its use)."""
    for p in db.execute(select(ExtraPasscode)).scalars():
        if verify_passcode(passcode, p.passcode_hash):
            p.last_used = utcnow()
            db.commit()
            return True
    return False


# ---------------------------------------------------------------- extra passcodes
class PasscodeIn(BaseModel):
    label: str = Field(..., min_length=1, max_length=80)
    passcode: str = Field(..., min_length=6, max_length=128)


def _pc_out(p: ExtraPasscode) -> dict:
    return {"id": p.id, "label": p.label, "created_by": p.created_by,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "last_used": p.last_used.isoformat() if p.last_used else None}


@router.get("/passcodes")
def list_passcodes(db: Session = Depends(get_db), user: Principal = Depends(require_admin)):
    return {"passcodes": [_pc_out(p) for p in db.execute(select(ExtraPasscode).order_by(ExtraPasscode.id)).scalars()]}


@router.post("/passcodes")
def add_passcode(body: PasscodeIn, db: Session = Depends(get_db), user: Principal = Depends(require_admin)):
    if check_extra_passcode(db, body.passcode):
        raise HTTPException(409, "That passcode is already in use")
    p = ExtraPasscode(label=body.label.strip(), passcode_hash=hash_passcode(body.passcode), created_by=user.username,
                      created_at=utcnow())
    db.add(p)
    db.commit()
    return _pc_out(p)


@router.delete("/passcodes/{pid}")
def delete_passcode(pid: int, db: Session = Depends(get_db), user: Principal = Depends(require_admin)):
    p = db.get(ExtraPasscode, pid)
    if p is None:
        raise HTTPException(404, "Passcode not found")
    db.delete(p)
    db.commit()
    return {"deleted": pid}


# ---------------------------------------------------------------- crew management
@router.get("/crew")
def crew(db: Session = Depends(get_db), user: Principal = Depends(require_admin)):
    logins = {u.astronaut_id: u.username for u in db.execute(select(User).where(User.astronaut_id.is_not(None))).scalars()}
    out = []
    for a in db.execute(select(Astronaut).order_by(Astronaut.id)).scalars():
        n, last = db.execute(select(func.count(Measurement.id), func.max(Measurement.timestamp))
                             .where(Measurement.astronaut_id == a.id)).one()
        alerts = db.execute(select(func.count(Alert.id)).where(Alert.astronaut_id == a.id, Alert.acknowledged.is_(False),
                                                               Alert.severity != "info")).scalar()
        out.append({"id": a.id, "callsign": a.callsign, "name": a.name, "role": a.role, "data_class": a.data_class,
                    "login": logins.get(a.id), "measurements": int(n or 0), "last_data": last.isoformat() if last else None,
                    "open_alerts": int(alerts or 0)})
    return {"crew": out}


class CrewIn(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=120)
    role: str | None = Field(None, min_length=1, max_length=120)
    passcode: str | None = Field(None, min_length=6, max_length=128)


@router.put("/crew/{astronaut_id}")
def update_crew(astronaut_id: str, body: CrewIn, db: Session = Depends(get_db), user: Principal = Depends(require_admin)):
    a = db.get(Astronaut, astronaut_id)
    if a is None:
        raise HTTPException(404, "Astronaut not found")
    login = db.execute(select(User).where(User.astronaut_id == astronaut_id)).scalars().first()
    if body.name:
        a.name = body.name.strip()
        if login:
            login.display_name = a.name
    if body.role:
        a.role = body.role.strip()
    if body.passcode:
        if login is None:
            raise HTTPException(404, "This astronaut has no login")
        login.passcode_hash = hash_passcode(body.passcode)
    db.commit()
    return {"id": a.id, "name": a.name, "role": a.role}
