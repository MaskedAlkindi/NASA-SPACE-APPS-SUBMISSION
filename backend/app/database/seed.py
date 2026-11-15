"""Idempotent demo seeding: mission, crew, users, simulated history, alerts."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_passcode
from app.database.models import Alert, Astronaut, Measurement, Mission, User
from app.intelligence import alerts as alert_engine
from app.intelligence.daily import astronaut_daily
from app.intelligence.ingest import store
from app.modules.registry import get_registry
from app.schemas.measurement import NormalizedMeasurement
from ml.datasets.synthetic import DEFAULT_CREW

log = logging.getLogger("hmt.seed")
MISSION_ID = "HMT-DEMO-1"
REAL_DEVICE_ID = "AST-900"


def seed_reference(db: Session) -> None:
    s = get_settings()
    if db.get(Mission, MISSION_ID) is None:
        start = datetime.now(timezone.utc).date() - timedelta(days=s.seed_days - 1)
        db.add(Mission(id=MISSION_ID, name="Lunar Gateway Expedition 1 (simulated demo mission)",
                       description="Fictional long-duration mission used to demonstrate HEALTH-01. All crew and data are simulated.",
                       start_date=start, planned_duration_days=180, vehicle="Gateway HALO module (simulated)",
                       data_class="simulated"))
        db.flush()
    for p in DEFAULT_CREW:
        a = db.get(Astronaut, p.astronaut_id)
        if a is None:
            db.add(Astronaut(id=p.astronaut_id, callsign=p.callsign, name=p.name, role=p.role,
                             mission_id=MISSION_ID, data_class="simulated"))
        elif a.callsign != p.callsign:          # crew renamed in a newer version: follow it
            a.callsign, a.name, a.role = p.callsign, p.name, p.role
    # Real-device test user: no simulated data, receives HealthKit / Health Connect uploads from the mobile apps.
    if db.get(Astronaut, REAL_DEVICE_ID) is None:
        db.add(Astronaut(id=REAL_DEVICE_ID, callsign="PILOT", name="Your wearable (real device data)",
                         role="Device test user", mission_id=MISSION_ID, data_class="real"))
    db.flush()
    users = [("mission-control", "Mission Control", "mission_control", None),
             ("flight-surgeon", "Flight Surgeon", "flight_surgeon", None),
             ("pilot", "PILOT (real device)", "astronaut", REAL_DEVICE_ID)]
    users += [(p.callsign.lower(), p.name, "astronaut", p.astronaut_id) for p in DEFAULT_CREW]
    wanted = {u[0] for u in users}
    crew_ids = {p.astronaut_id for p in DEFAULT_CREW}
    for old in db.execute(select(User).where(User.astronaut_id.in_(crew_ids))).scalars().all():
        if old.username not in wanted:          # logins from an older crew list
            db.delete(old)
    db.flush()
    for username, display, role, aid in users:
        if db.get(User, username) is None:
            db.add(User(username=username, display_name=display, role=role, astronaut_id=aid,
                        passcode_hash=hash_passcode(s.demo_passcode)))
    db.commit()


def seed_history(db: Session, force: bool = False) -> int:
    s = get_settings()
    n = db.execute(select(func.count(Measurement.id))).scalar()
    only = None
    if n and not force:
        # a crew member added in a newer version (e.g. AST-005) gets history; everyone else keeps theirs
        have = {r[0] for r in db.execute(select(Measurement.astronaut_id).distinct())}
        only = {p.astronaut_id for p in DEFAULT_CREW} - have
        if not only:
            return 0
    if force:
        db.execute(delete(Measurement).where(Measurement.data_class == "simulated"))
        db.execute(delete(Alert).where(Alert.data_class == "simulated"))
        db.commit()
    sim = get_registry().get("simulation")
    if sim is None:
        log.warning("simulation module unavailable - no demo data seeded")
        return 0
    records = sim.seed_records(s.seed_days)
    if only is not None:
        records = [r for r in records if r.get("astronaut_id") in only]
    items, errors = sim.ingest(records)
    if errors:
        log.warning("%d seed records rejected, e.g. %s", len(errors), errors[:2])
    store(db, items)
    # Historical alert evaluation for the last 21 days so the timeline is populated.
    for p in DEFAULT_CREW:
        if only is not None and p.astronaut_id not in only:
            continue
        daily = astronaut_daily(db, p.astronaut_id, days=s.seed_days + 5)
        for k in range(max(10, len(daily) - 21), len(daily) + 1):
            alert_engine.persist(db, alert_engine.evaluate_astronaut(daily.iloc[:k], p.astronaut_id), "simulated")
    if only is None:
        alert_engine.persist(db, alert_engine.evaluate_environment(db), "simulated")
    log.info("seeded %d simulated measurements", len(items))
    return len(items)
