"""Server connections (/api/v1/servers): operator-managed links to other servers and online data.

Connector logic lives in the top-level servers/ package; this file only stores what the operator added and calls it.
All settings are stored locally in this installation's database.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import Principal, current_user, require_crew_wide
from app.database.session import get_db
from app.devices.db_models import ServerConnection

router = APIRouter(prefix="/api/v1/servers", tags=["servers"])
SECRET_KEYS = {"token", "api_key", "password"}


def _connectors():
    from servers.registry import all_connectors
    return all_connectors()


def _out(c: ServerConnection) -> dict:
    return {"id": c.id, "name": c.name, "kind": c.kind, "url": c.url, "enabled": c.enabled,
            "settings": {k: ("•••" if k in SECRET_KEYS and v else v) for k, v in (c.settings or {}).items()},
            "last_checked": c.last_checked.isoformat() if c.last_checked else None, "last_status": c.last_status,
            "last_message": c.last_message, "last_data": c.last_data or {}}


@router.get("/connectors")
def connectors(user: Principal = Depends(current_user)):
    return {"connectors": [c.describe() for c in _connectors().values()]}


@router.get("")
def list_connections(db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    rows = db.execute(select(ServerConnection).order_by(ServerConnection.id)).scalars().all()
    return {"connections": [_out(c) for c in rows]}


class ConnIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    kind: str
    url: str = Field(..., min_length=8, max_length=2000)
    enabled: bool = True
    settings: dict = Field(default_factory=dict)


def _check(db: Session, c: ServerConnection) -> ServerConnection:
    from servers.registry import run_check
    try:
        r = run_check(c.kind, c.url, c.settings or {})
        c.last_status, c.last_message, c.last_data = ("ok" if r.ok else "error"), r.message[:500], r.data
    except Exception as e:   # noqa: BLE001 - shown to the operator
        c.last_status, c.last_message = "error", f"{type(e).__name__}: {str(e)[:300]}"
    c.last_checked = datetime.now(timezone.utc)
    db.commit()
    return c


@router.post("")
def add_connection(body: ConnIn, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    if body.kind not in _connectors():
        raise HTTPException(422, f"unknown connector kind '{body.kind}'")
    c = ServerConnection(name=body.name, kind=body.kind, url=body.url.strip(), enabled=body.enabled,
                         settings=body.settings, created_by=user.username)
    db.add(c)
    db.commit()
    return {"connection": _out(_check(db, c))}


@router.put("/{conn_id}")
def update_connection(conn_id: int, body: ConnIn, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    c = db.get(ServerConnection, conn_id)
    if c is None:
        raise HTTPException(404, "connection not found")
    if body.kind not in _connectors():
        raise HTTPException(422, f"unknown connector kind '{body.kind}'")
    settings = dict(c.settings or {})
    for k, v in body.settings.items():
        if not (k in SECRET_KEYS and v == "•••"):      # keep stored secret when the UI sends the mask back
            settings[k] = v
    c.name, c.kind, c.url, c.enabled, c.settings = body.name, body.kind, body.url.strip(), body.enabled, settings
    db.commit()
    return {"connection": _out(_check(db, c))}


@router.post("/{conn_id}/check")
def check_connection(conn_id: int, db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    c = db.get(ServerConnection, conn_id)
    if c is None:
        raise HTTPException(404, "connection not found")
    return {"connection": _out(_check(db, c))}


@router.delete("/{conn_id}")
def delete_connection(conn_id: int, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    c = db.get(ServerConnection, conn_id)
    if c is None:
        raise HTTPException(404, "connection not found")
    db.delete(c)
    db.commit()
    return {"deleted": conn_id}
