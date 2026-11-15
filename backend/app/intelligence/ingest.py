"""Persist normalised measurements, then run alert evaluation for affected astronauts."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import broadcaster
from app.database.models import Alert, Measurement
from app.intelligence import alerts as alert_engine
from app.intelligence.daily import astronaut_daily
from app.schemas.measurement import NormalizedMeasurement
from app.schemas.metrics import METRICS

NON_TRIGGER = {"heart_rate"}   # high-frequency stream; daily metrics trigger evaluation


def store(db: Session, items: list[NormalizedMeasurement]) -> tuple[int, int]:
    inserted = updated = 0
    new_rows = []
    for m in items:
        if m.external_id:
            existing = db.execute(select(Measurement).where(
                Measurement.source_module == m.source_module, Measurement.astronaut_id == m.astronaut_id,
                Measurement.external_id == m.external_id)).scalar_one_or_none()
            if existing:
                existing.value, existing.value_json, existing.timestamp = m.value, m.value_json, m.timestamp
                existing.quality, existing.source_device = m.quality.value, m.source_device
                updated += 1
                continue
        new_rows.append(Measurement(
            astronaut_id=m.astronaut_id, metric=m.metric, value=m.value, value_json=m.value_json, unit=m.unit,
            timestamp=m.timestamp, source_device=m.source_device, source_module=m.source_module,
            quality=m.quality.value, data_class=m.data_class.value, external_id=m.external_id))
        inserted += 1
    db.add_all(new_rows)
    db.commit()
    return inserted, updated


def alert_out(a: Alert) -> dict:
    return {"id": a.id, "astronaut_id": a.astronaut_id, "severity": a.severity, "category": a.category,
            "title": a.title, "message": a.message, "evidence": a.evidence, "recommendation": a.recommendation,
            "source": a.source, "data_class": a.data_class, "observed_at": a.observed_at.isoformat() if a.observed_at else None,
            "created_at": a.created_at.isoformat() if a.created_at else None, "acknowledged": a.acknowledged}


def evaluate_after_ingest(db: Session, items: list[NormalizedMeasurement]) -> list[Alert]:
    astronauts = {m.astronaut_id for m in items if m.astronaut_id and m.metric not in NON_TRIGGER}
    env = any(not METRICS[m.metric].per_astronaut for m in items)
    data_class = "real" if any(m.data_class.value == "real" for m in items) else items[0].data_class.value if items else "simulated"
    created: list[Alert] = []
    for aid in sorted(astronauts):
        daily = astronaut_daily(db, aid)
        created += alert_engine.persist(db, alert_engine.evaluate_astronaut(daily, aid), data_class)
    if env:
        created += alert_engine.persist(db, alert_engine.evaluate_environment(db), data_class)
    # Plug-in AI engine (ai/): runs enabled models; failures are contained inside after_ingest.
    from app.ai_engine.service import after_ingest
    created += after_ingest(db, astronauts, {m.metric for m in items})
    return created


def ingest(db: Session, items: list[NormalizedMeasurement], publish: bool = True) -> dict:
    inserted, updated = store(db, items)
    created = evaluate_after_ingest(db, items) if items else []
    if publish and items:
        broadcaster.publish({"type": "measurements", "items": [
            {"astronaut_id": m.astronaut_id, "metric": m.metric, "value": m.value, "unit": m.unit,
             "timestamp": m.timestamp.isoformat(), "data_class": m.data_class.value} for m in items[:400]]})
        for a in created:
            broadcaster.publish({"type": "alert", "alert": alert_out(a)})
    return {"accepted": inserted, "updated": updated, "alerts": created}
