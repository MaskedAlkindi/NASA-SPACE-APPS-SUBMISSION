"""Habitat sensors over MQTT (/api/v1/mqtt). Reading is open to signed-in users; changes need a crew-wide role."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import Principal, current_user, require_crew_wide
from app.database.session import get_db
from app.mqtt import bridge
from app.mqtt.db_models import MqttBroker, MqttMapping
from app.mqtt.sim_pipeline import install as install_sim_pipeline

router = APIRouter(prefix="/api/v1/mqtt", tags=["habitat mqtt"])

# Handy conversions shown in the UI (value = raw * scale + offset)
PRESETS = [
    {"label": "none", "scale": 1, "offset": 0},
    {"label": "CO₂ ppm → mmHg (at 101.3 kPa)", "scale": 0.00076, "offset": 0},
    {"label": "hPa → kPa", "scale": 0.1, "offset": 0},
    {"label": "Pa → kPa", "scale": 0.001, "offset": 0},
    {"label": "°F → °C", "scale": 0.5555556, "offset": -17.7777778},
    {"label": "µSv/h → µGy/h (photons, 1:1)", "scale": 1, "offset": 0},
]


def _broker(db: Session) -> MqttBroker:
    b = db.get(MqttBroker, 1)
    if b is None:
        b = MqttBroker(id=1)
        db.add(b)
        db.commit()
    return b


def _b_out(b: MqttBroker) -> dict:
    return {"host": b.host, "port": b.port, "username": b.username, "password": "•••" if b.password else "", "tls": b.tls,
            "discover": b.discover, "enabled": b.enabled}


def _m_out(m: MqttMapping) -> dict:
    return {k: getattr(m, k) for k in ("id", "topic", "metric", "json_path", "scale", "offset", "astronaut_id", "data_class",
                                       "min_interval_s", "label", "enabled", "last_value", "last_error")} | \
           {"last_at": m.last_at.isoformat() if m.last_at else None}


@router.get("")
def overview(db: Session = Depends(get_db), user: Principal = Depends(current_user)):
    from app.schemas.metrics import METRICS
    maps = db.execute(select(MqttMapping).order_by(MqttMapping.id)).scalars().all()
    metrics = [{"metric": k, "label": m.label, "unit": m.unit, "environment": not m.per_astronaut} for k, m in METRICS.items()]
    return {"broker": _b_out(_broker(db)), "status": bridge.status(), "mappings": [_m_out(m) for m in maps],
            "seen": bridge.seen_topics(), "metrics": metrics, "presets": PRESETS}


class BrokerIn(BaseModel):
    host: str = Field(..., min_length=1, max_length=255)
    port: int = Field(1883, ge=1, le=65535)
    username: str = Field("", max_length=120)
    password: str = Field("", max_length=500)
    tls: bool = False
    discover: str = Field("habitat/#", max_length=255)
    enabled: bool = True


class SimPipelineIn(BaseModel):
    host: str = Field("mosquitto", min_length=1, max_length=255)
    port: int = Field(1883, ge=1, le=65535)


@router.post("/sim-pipeline")
def sim_pipeline(body: SimPipelineIn, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    """Connect the broker and assign the mqtt-sim publisher topics as simulated measurements."""
    rows = install_sim_pipeline(db, body.host, body.port)
    return {"broker": _b_out(_broker(db)), "status": bridge.start(), "installed": [_m_out(m) for m in rows]}


@router.put("/broker")
def set_broker(body: BrokerIn, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    b = _broker(db)
    b.host, b.port, b.username, b.tls, b.discover, b.enabled = body.host.strip(), body.port, body.username, body.tls, body.discover.strip(), body.enabled
    if body.password != "•••":
        b.password = body.password
    b.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"broker": _b_out(b), "status": bridge.start()}


class MappingIn(BaseModel):
    topic: str = Field(..., min_length=1, max_length=255)
    metric: str
    json_path: str = Field("", max_length=255)
    scale: float = 1.0
    offset: float = 0.0
    astronaut_id: str | None = None
    data_class: str = Field("real", pattern="^(real|simulated)$")
    min_interval_s: float = Field(10.0, ge=0, le=86400)
    label: str = Field("", max_length=120)
    enabled: bool = True


def _check(body: MappingIn, db: Session) -> None:
    from app.database.models import Astronaut
    from app.schemas.metrics import METRICS
    if body.metric not in METRICS:
        raise HTTPException(422, f"unknown metric '{body.metric}'")
    if METRICS[body.metric].per_astronaut and not body.astronaut_id:
        raise HTTPException(422, "this metric belongs to a person: choose the crew member")
    if body.astronaut_id and db.get(Astronaut, body.astronaut_id) is None:
        raise HTTPException(422, "unknown astronaut")


@router.post("/mappings")
def add_mapping(body: MappingIn, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    _check(body, db)
    m = MqttMapping(**body.model_dump())
    db.add(m)
    db.commit()
    bridge.resubscribe()
    return {"mapping": _m_out(m)}


@router.put("/mappings/{mid}")
def update_mapping(mid: int, body: MappingIn, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    m = db.get(MqttMapping, mid)
    if m is None:
        raise HTTPException(404, "mapping not found")
    _check(body, db)
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    db.commit()
    bridge.resubscribe()
    return {"mapping": _m_out(m)}


@router.delete("/mappings/{mid}")
def delete_mapping(mid: int, db: Session = Depends(get_db), user: Principal = Depends(require_crew_wide)):
    m = db.get(MqttMapping, mid)
    if m is None:
        raise HTTPException(404, "mapping not found")
    db.delete(m)
    db.commit()
    return {"deleted": mid}


class TestIn(BaseModel):
    payload: str = Field(..., max_length=2000)
    json_path: str = ""
    scale: float = 1.0
    offset: float = 0.0


@router.post("/preview")
def preview(body: TestIn, user: Principal = Depends(current_user)):
    """Try a JSON path and conversion on a sample payload before saving."""
    try:
        v = bridge.extract(body.payload.encode(), body.json_path) * body.scale + body.offset
        return {"ok": True, "value": round(v, 4)}
    except Exception as e:   # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
