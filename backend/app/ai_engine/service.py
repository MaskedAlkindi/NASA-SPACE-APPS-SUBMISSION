"""Glue between the AI engine (ai/) and the backend: registry singleton, persistence, alerts.

Environment:
  HMT_AI_ENABLED=true      turn the engine off entirely (the original ml/ models keep working)
  HMT_AI_ON_INGEST=true    run enabled models after new daily measurements arrive
  HMT_AI_INGEST_DELAY_S=30 quiet period before a queued run (bursts are coalesced)
"""
from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.adapters.alerts import to_event
from ai.core.types import Assessment
from ai.registry.registry import ModelRegistry
from app.ai_engine.data_view import BackendHealthDataView
from app.ai_engine.db_models import AiAssessment, AiModelState
from app.database.models import Alert
from app.database.session import SessionLocal

log = logging.getLogger("hmt.ai")
ENABLED = os.getenv("HMT_AI_ENABLED", "true").lower() != "false"
ON_INGEST = os.getenv("HMT_AI_ON_INGEST", "true").lower() != "false"


class DbStateStore:
    def get(self, model_id):
        db = SessionLocal()
        try:
            row = db.get(AiModelState, model_id)
            return dict(row.state) if row else None
        finally:
            db.close()

    def set(self, model_id, state, user: str = ""):
        db = SessionLocal()
        try:
            row = db.get(AiModelState, model_id) or AiModelState(model_id=model_id)
            row.state = dict(state)
            row.updated_by = user
            row.updated_at = datetime.now(timezone.utc)
            db.merge(row)
            db.commit()
        finally:
            db.close()


_registry: ModelRegistry | None = None


def registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry(state=DbStateStore())
    return _registry


def _persist(db: Session, a: Assessment) -> None:
    db.add(AiAssessment(astronaut_id=a.astronaut_id, model_id=a.model_id, model_version=a.model_version,
                        assessed_at=a.assessed_at, status=a.status, category=a.category, severity=a.severity,
                        score=a.score, payload=a.model_dump(mode="json")))


def _alert(db: Session, a: Assessment) -> Alert | None:
    """Concerns become alerts in the existing alert system; insights stay as assessments."""
    reg = registry()
    m = reg.entries[a.model_id].manifest
    policy = m.alerting.model_copy(update={"thresholds": reg.settings(a.model_id)["thresholds"]})
    ev = to_event(a, m, policy)
    if ev is None or ev["kind"] != "concern":
        return None
    if db.execute(select(Alert.id).where(Alert.dedupe_key == ev["dedupe_key"])).first():
        return None
    when = datetime.fromisoformat(f"{a.data_as_of}T12:00:00+00:00") if a.data_as_of else a.assessed_at
    al = Alert(astronaut_id=a.astronaut_id, severity=a.severity, category=a.category,
               title=f"{m.name}: {a.score_label or a.severity}",
               message=f"{a.explanation} ({ev['evidence_note']})",
               evidence=[{"metric": c.metric, "value": c.value, "unit": c.unit, "baseline_median": c.baseline, "z": c.deviation,
                          "note": c.note} for c in a.contributing],
               recommendation=a.recommendation, source=f"ai:{a.model_id}@{a.model_version}",
               dedupe_key=ev["dedupe_key"], data_class=(BackendHealthDataView(db, a.astronaut_id).profile().get("data_class") or "simulated"),
               observed_at=when)
    db.add(al)
    return al


def run_for(db: Session, astronaut_id: str, model_ids: list[str] | None = None, persist: bool = True,
            emit_alerts: bool = True) -> tuple[list[Assessment], list[Alert]]:
    if not ENABLED:
        return [], []
    view = BackendHealthDataView(db, astronaut_id)
    results = registry().run_all(view, model_ids)
    alerts: list[Alert] = []
    if persist:
        for a in results:
            if a.status != "disabled":
                _persist(db, a)
            if emit_alerts:
                al = _alert(db, a)
                if al is not None:
                    alerts.append(al)
        db.commit()
    return results, alerts


def latest(db: Session, astronaut_id: str) -> list[dict]:
    rows = db.execute(select(AiAssessment).where(AiAssessment.astronaut_id == astronaut_id)
                      .order_by(AiAssessment.assessed_at.desc()).limit(200)).scalars()
    seen, out = set(), []
    for r in rows:
        if r.model_id not in seen:
            seen.add(r.model_id)
            out.append(r.payload)
    return out


TRIGGER_METRICS = {"resting_heart_rate", "sleep_duration", "hrv_sdnn", "hrv_rmssd", "blood_glucose", "fasting_insulin",
                   "fatigue_score", "exercise_minutes"}
# Debounced background worker: a burst of uploads (or the simulator) for one astronaut is coalesced
# into a single run once the burst has been quiet for INGEST_DELAY_S. Daemon thread, so it never
# blocks shutdown, and at most one astronaut is processed at a time.
INGEST_DELAY_S = float(os.getenv("HMT_AI_INGEST_DELAY_S", "30"))
INGEST_MAX_WAIT_S = float(os.getenv("HMT_AI_INGEST_MAX_WAIT_S", "120"))   # a steady stream can't postpone forever
_due: dict[str, float] = {}
_first: dict[str, float] = {}
_cv = threading.Condition()
_worker: threading.Thread | None = None


def _worker_loop() -> None:
    while True:
        with _cv:
            while not _due:
                _cv.wait()
            aid, t = min(_due.items(), key=lambda kv: kv[1])
            wait = t - time.monotonic()
            if wait > 0:
                _cv.wait(timeout=wait)
                continue
            del _due[aid]
            _first.pop(aid, None)
        _background_run(aid)


def schedule_now(astronaut_ids) -> None:
    """Run the models for these astronauts as soon as the worker is free (used by the simulator at day end)."""
    if not ENABLED:
        return
    for aid in astronaut_ids:
        _schedule(aid, delay=0.0)


def warm_up() -> list[str]:
    """Load every enabled model at startup so the first request is fast. Errors are logged, never raised."""
    if not ENABLED:
        return []
    reg, loaded = registry(), []
    for mid in reg.enabled_ids():
        try:
            reg.plugin(mid).load()
            loaded.append(mid)
        except Exception:   # noqa: BLE001
            log.exception("could not preload model %s", mid)
    log.info("AI models loaded: %s", ", ".join(loaded))
    return loaded


def _schedule(aid: str, delay: float | None = None) -> None:
    global _worker
    with _cv:
        now = time.monotonic()
        first = _first.setdefault(aid, now)
        _due[aid] = now if delay == 0.0 else min(now + INGEST_DELAY_S, first + INGEST_MAX_WAIT_S)   # debounce, capped
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_worker_loop, name="ai-ingest", daemon=True)
            _worker.start()
        _cv.notify()
    log.debug("AI run for %s queued (in %.0fs)", aid, INGEST_DELAY_S)


def _background_run(aid: str) -> None:
    from app.core.events import broadcaster
    from app.intelligence.ingest import alert_out
    db = SessionLocal()
    try:
        results, alerts = run_for(db, aid)
        log.info("AI run for %s after ingest: %d assessments, %d alerts", aid, len(results), len(alerts))
        for a in alerts:
            broadcaster.publish({"type": "alert", "alert": alert_out(a)})
    except Exception:   # noqa: BLE001 - AI must never break ingestion
        db.rollback()
        log.exception("AI engine failed for %s", aid)
    finally:
        db.close()


def after_ingest(db: Session, astronaut_ids: set[str], metrics: set[str] | None = None) -> list[Alert]:
    """Called by the ingestion pipeline. Queues a background run per astronaut when daily summary
    metrics arrive; never blocks or raises. Returns [] (alerts are published when the run finishes)."""
    if not (ENABLED and ON_INGEST):
        return []
    if metrics is not None and not (metrics & TRIGGER_METRICS):
        return []
    for aid in sorted(astronaut_ids):
        _schedule(aid)
    return []
