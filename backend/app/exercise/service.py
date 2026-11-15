"""Persistence and health-system integration for workouts.

Sessions live in exercise tables. Completed sessions can also emit
``exercise_minutes`` (and heart rate, when the user typed one) through the
shared ingestion path so the existing activity domain and alert rules see them.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.events import broadcaster
from app.database.models import Alert, Astronaut, ExerciseAssignment, ExerciseGoal, ExerciseProfile, Measurement, Mission, WorkoutSession
from app.exercise import CONTRACT_VERSION, DISCLAIMER
from app.exercise.catalog import CATALOG
from app.exercise.goals import daily_series, evaluate_goals, missed_dates, streak_days, weekly_adherence
from app.exercise.programs import GENERAL, MISSION, personalize
from app.exercise.recommendations import recommend
from app.intelligence.ingest import ingest
from app.schemas.measurement import DataClass, NormalizedMeasurement, Quality

log = logging.getLogger("hmt.exercise")

DEFAULT_GOALS = [
    ("day", "minutes", 60, "Daily minutes (example)"),
    ("week", "sessions", 6, "Weekly sessions (example)"),
    ("month", "sessions", 24, "Monthly sessions (example)"),
    ("year", "sessions", 250, "Yearly sessions (example)"),
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def profile_dict(row: ExerciseProfile) -> dict:
    return {
        "astronaut_id": row.astronaut_id, "fitness_level": row.fitness_level, "focus": row.focus,
        "limitations": row.limitations or "", "equipment": list(row.equipment or []),
        "mission_phase": row.mission_phase, "notes": row.notes or "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def ensure_profile(db: Session, astronaut_id: str) -> ExerciseProfile:
    row = db.get(ExerciseProfile, astronaut_id)
    if row is None:
        row = ExerciseProfile(astronaut_id=astronaut_id, fitness_level="intermediate", focus="balanced",
                              limitations="", equipment=["bodyweight", "bands", "cycle"], mission_phase="in_flight", notes="")
        db.add(row)
        db.flush()
    if db.execute(select(func.count()).select_from(ExerciseGoal).where(ExerciseGoal.astronaut_id == astronaut_id)).scalar() == 0:
        for period, metric, target, label in DEFAULT_GOALS:
            db.add(ExerciseGoal(astronaut_id=astronaut_id, period=period, metric=metric, target=target, label=label, example_only=True))
    _ensure_assignment(db, astronaut_id, profile_dict(row))
    db.commit()
    db.refresh(row)
    return row


def _ensure_assignment(db: Session, astronaut_id: str, profile: dict) -> None:
    kinds = {r.kind for r in db.execute(select(ExerciseAssignment).where(
        ExerciseAssignment.astronaut_id == astronaut_id, ExerciseAssignment.active.is_(True))).scalars()}
    if "general" not in kinds:
        db.add(ExerciseAssignment(astronaut_id=astronaut_id, program_id=GENERAL["id"], kind="general",
                                  active=True, program_snapshot=GENERAL))
    if "mission" not in kinds:
        db.add(ExerciseAssignment(astronaut_id=astronaut_id, program_id=MISSION["id"], kind="mission",
                                  active=True, program_snapshot=MISSION))
    if "personalized" not in kinds:
        program = personalize({**profile, "astronaut_id": astronaut_id})
        db.add(ExerciseAssignment(astronaut_id=astronaut_id, program_id=program["id"], kind="personalized",
                                  active=True, program_snapshot=program))


def save_profile(db: Session, astronaut_id: str, fields: dict) -> ExerciseProfile:
    row = ensure_profile(db, astronaut_id)
    for key in ("fitness_level", "focus", "limitations", "equipment", "mission_phase", "notes"):
        if key in fields and fields[key] is not None:
            setattr(row, key, fields[key])
    row.updated_at = _utcnow()
    program = personalize(profile_dict(row))
    for old in db.execute(select(ExerciseAssignment).where(
            ExerciseAssignment.astronaut_id == astronaut_id, ExerciseAssignment.kind == "personalized",
            ExerciseAssignment.active.is_(True))).scalars():
        old.active = False
    db.add(ExerciseAssignment(astronaut_id=astronaut_id, program_id=program["id"], kind="personalized",
                              active=True, program_snapshot=program))
    db.commit()
    db.refresh(row)
    return row


def active_programs(db: Session, astronaut_id: str) -> dict[str, dict]:
    ensure_profile(db, astronaut_id)
    rows = db.execute(select(ExerciseAssignment).where(
        ExerciseAssignment.astronaut_id == astronaut_id, ExerciseAssignment.active.is_(True))
        .order_by(ExerciseAssignment.id.asc())).scalars()
    return {r.kind: r.program_snapshot for r in rows}


def goals_for(db: Session, astronaut_id: str) -> list[ExerciseGoal]:
    ensure_profile(db, astronaut_id)
    return list(db.execute(select(ExerciseGoal).where(ExerciseGoal.astronaut_id == astronaut_id).order_by(ExerciseGoal.id)).scalars())


def replace_goals(db: Session, astronaut_id: str, goals: list[dict]) -> list[ExerciseGoal]:
    ensure_profile(db, astronaut_id)
    db.execute(delete(ExerciseGoal).where(ExerciseGoal.astronaut_id == astronaut_id))
    for g in goals:
        db.add(ExerciseGoal(astronaut_id=astronaut_id, period=g["period"], metric=g["metric"],
                            target=g["target"], label=g["label"], example_only=True))
    db.commit()
    return goals_for(db, astronaut_id)


def _session_minutes(started: datetime, ended: datetime | None) -> float:
    if ended is None:
        return 1.0
    minutes = (as_utc(ended) - as_utc(started)).total_seconds() / 60
    if minutes <= 0:
        return 1.0
    return float(min(600, round(max(minutes, 1.0), 1)))


def _reps(exercises: list[dict]) -> int:
    total = 0
    for ex in exercises:
        for s in ex.get("sets") or []:
            if s.get("reps"):
                total += int(s["reps"])
    return total


def session_out(row: WorkoutSession) -> dict:
    started = as_utc(row.started_at)
    return {
        "contract_version": CONTRACT_VERSION,
        "id": row.id, "astronaut_id": row.astronaut_id, "program_id": row.program_id,
        "source": row.source, "status": row.status,
        "started_at": started.isoformat(),
        "ended_at": as_utc(row.ended_at).isoformat() if row.ended_at else None,
        "exercises": row.exercises or [], "summary": row.summary or {},
        "perceived_exertion": row.perceived_exertion, "heart_rate_avg": row.heart_rate_avg,
        "notes": row.notes or "", "data_class": row.data_class, "client_id": row.client_id,
        "sync_health": row.sync_health, "example_only": False,
    }


def list_sessions(db: Session, astronaut_id: str, limit: int = 200) -> list[WorkoutSession]:
    ensure_profile(db, astronaut_id)
    return list(db.execute(select(WorkoutSession).where(WorkoutSession.astronaut_id == astronaut_id)
                           .order_by(WorkoutSession.started_at.desc()).limit(limit)).scalars())


def _plain(row: WorkoutSession) -> dict:
    return {"date": as_utc(row.started_at).date(), "minutes": float((row.summary or {}).get("minutes") or 0),
            "status": row.status}


def record_session(db: Session, astronaut_id: str, body: dict, *, data_class: str, emit_alerts: bool = True) -> WorkoutSession:
    if body.get("client_id"):
        existing = db.execute(select(WorkoutSession).where(
            WorkoutSession.astronaut_id == astronaut_id, WorkoutSession.client_id == body["client_id"])).scalar_one_or_none()
        if existing:
            return existing
    for ex in body["exercises"]:
        if ex["exercise_id"] not in CATALOG:
            raise KeyError(ex["exercise_id"])
    started = as_utc(body["started_at"])
    ended = as_utc(body["ended_at"]) if body.get("ended_at") else None
    if ended and ended < started:
        raise ValueError("ended_at is before started_at")
    minutes = _session_minutes(started, ended)
    exercises = body["exercises"]
    categories = []
    for ex in exercises:
        cat = CATALOG[ex["exercise_id"]].category
        if cat not in categories:
            categories.append(cat)
    summary = dict(body.get("summary") or {})
    summary.update({
        "minutes": minutes, "reps": summary.get("reps", _reps(exercises)), "example_only": False,
        "kind": categories[0] if len(categories) == 1 else "mixed",
    })
    row = WorkoutSession(
        astronaut_id=astronaut_id, program_id=body.get("program_id"), source=body.get("source") or "manual",
        status="completed", started_at=started, ended_at=ended, exercises=exercises, summary=summary,
        perceived_exertion=body.get("perceived_exertion"), heart_rate_avg=body.get("heart_rate_avg"),
        notes=(body.get("notes") or "")[:2000], data_class=data_class, client_id=body.get("client_id"),
        sync_health=bool(body.get("sync_health", True)))
    db.add(row)
    db.flush()
    if row.sync_health:
        _sync_health(db, row)
    db.commit()
    db.refresh(row)
    if emit_alerts:
        _review_session(db, row)
        refresh_adherence_alerts(db, astronaut_id)
    return row


def _sync_health(db: Session, row: WorkoutSession) -> None:
    minutes = float((row.summary or {}).get("minutes") or 0)
    items = [NormalizedMeasurement(
        astronaut_id=row.astronaut_id, metric="exercise_minutes", value=minutes, unit="min",
        timestamp=as_utc(row.ended_at or row.started_at), source_device=f"exercise-{row.source}",
        source_module="exercise", quality=Quality.good if row.source == "manual" else Quality.fair,
        data_class=DataClass(row.data_class), external_id=f"exercise:{row.id}:minutes")]
    if row.heart_rate_avg is not None:
        items.append(NormalizedMeasurement(
            astronaut_id=row.astronaut_id, metric="heart_rate", value=float(row.heart_rate_avg), unit="bpm",
            timestamp=as_utc(row.ended_at or row.started_at), source_device=f"exercise-{row.source}",
            source_module="exercise", quality=Quality.fair, data_class=DataClass(row.data_class),
            external_id=f"exercise:{row.id}:hr"))
    try:
        ingest(db, items)
    except Exception:
        log.exception("exercise session %s could not sync measurements", row.id)


def _add_alert(db: Session, astronaut_id: str, dedupe: str, severity: str, title: str, message: str,
               evidence: list, recommendation: str, data_class: str) -> None:
    if db.execute(select(Alert.id).where(Alert.dedupe_key == dedupe)).first():
        return
    alert = Alert(astronaut_id=astronaut_id, severity=severity, category="exercise", title=title, message=message,
                  evidence=evidence, recommendation=recommendation, source="rule:exercise-review", dedupe_key=dedupe,
                  data_class=data_class, observed_at=_utcnow())
    db.add(alert)
    db.commit()
    db.refresh(alert)
    try:
        from app.intelligence.ingest import alert_out
        broadcaster.publish({"type": "alert", "alert": alert_out(alert)})
    except Exception:
        log.debug("exercise alert was stored but not published", exc_info=True)


def _resting_hr(db: Session, astronaut_id: str) -> float | None:
    try:
        from app.intelligence.daily import astronaut_daily
        daily = astronaut_daily(db, astronaut_id, days=14)
    except Exception:
        log.debug("no daily frame for exercise HR review", exc_info=True)
        return None
    if daily is None or daily.empty or "resting_heart_rate" not in daily.columns:
        return None
    series = daily["resting_heart_rate"].dropna()
    if series.empty:
        return None
    return float(series.iloc[-1])


def _review_session(db: Session, row: WorkoutSession) -> None:
    hr = row.heart_rate_avg
    if hr is None:
        return
    resting = _resting_hr(db, row.astronaut_id)
    unusual = hr >= 175 or (resting is not None and hr >= resting + 50 and hr >= 140)
    if not unusual:
        return
    _add_alert(
        db, row.astronaut_id, f"{row.astronaut_id}:exercise_hr:{row.id}", "caution",
        "Exercise heart rate needs a look",
        f"The logged session average heart rate was {hr:.0f} bpm. This is a review flag, not a diagnosis.",
        [{"metric": "heart_rate", "value": round(float(hr), 1), "unit": "bpm",
          "note": None if resting is None else f"latest resting HR {resting:.0f} bpm"}],
        "Ask the crew medical officer to review this session. Do not treat this message as a training change.",
        row.data_class)


def refresh_adherence_alerts(db: Session, astronaut_id: str) -> None:
    """One alert for yesterday's missed example session, and one if this week's adherence is low."""
    try:
        programs = active_programs(db, astronaut_id)
        personal = programs.get("personalized") or programs.get("general") or {}
        weekdays = (personal.get("schedule") or {}).get("weekdays") or [0, 1, 2, 3, 4, 5]
        rows = list_sessions(db, astronaut_id, limit=400)
        dates = [as_utc(r.started_at).date() for r in rows if r.status == "completed"]
        today = _utcnow().date()
        missed = missed_dates(dates, weekdays, today - timedelta(days=7), today, today)
        yesterday = (today - timedelta(days=1)).isoformat()
        astro = db.get(Astronaut, astronaut_id)
        data_class = astro.data_class if astro else "simulated"
        if yesterday in missed:
            _add_alert(db, astronaut_id, f"{astronaut_id}:exercise_missed:{yesterday}", "info",
                       "Missed example session",
                       f"No workout was logged on {yesterday}, which is a scheduled day on the example program.",
                       [{"metric": "exercise_minutes", "value": 0, "unit": "min", "note": "no logged session"}],
                       "This is an adherence note for the demo program, not a medical finding.", data_class)
        weeks = weekly_adherence(dates, float((personal.get("schedule") or {}).get("sessions_per_week") or 6), today, weeks=1)
        if weeks and today.weekday() >= 2 and weeks[-1]["pct"] < 50:
            _add_alert(db, astronaut_id, f"{astronaut_id}:exercise_adherence:{weeks[-1]['week_start']}", "caution",
                       "Exercise adherence is low this week",
                       f"Logged sessions cover {weeks[-1]['pct']}% of the example weekly target so far.",
                       [{"metric": "exercise_minutes", "value": weeks[-1]["sessions"], "unit": "sessions",
                         "note": "sessions this week vs example target"}],
                       "A lighter example session is available on the Exercise page. This is not a prescription.",
                       data_class)
    except Exception:
        log.exception("adherence alerts skipped for %s", astronaut_id)


def progress_report(db: Session, astronaut_id: str) -> dict:
    ensure_profile(db, astronaut_id)
    refresh_adherence_alerts(db, astronaut_id)
    rows = list_sessions(db, astronaut_id, limit=500)
    plain = [_plain(r) for r in rows if r.status == "completed"]
    today = _utcnow().date()
    goal_rows = [{"period": g.period, "metric": g.metric, "target": g.target, "label": g.label, "example_only": g.example_only}
                 for g in goals_for(db, astronaut_id)]
    programs = active_programs(db, astronaut_id)
    personal = programs.get("personalized") or {}
    weekdays = (personal.get("schedule") or {}).get("weekdays") or [0, 1, 2, 3, 4, 5]
    dates = [p["date"] for p in plain]
    weekly_target = float(next((g["target"] for g in goal_rows if g["period"] == "week" and g["metric"] == "sessions"), 6))
    wearable = _wearable_minutes(db, astronaut_id, today)
    return {
        "contract_version": CONTRACT_VERSION,
        "astronaut_id": astronaut_id,
        "streak_days": streak_days(dates, today),
        "missed_dates": missed_dates(dates, weekdays, today - timedelta(days=35), today, today),
        "goals": evaluate_goals(plain, goal_rows, today),
        "adherence_weeks": weekly_adherence(dates, weekly_target, today),
        "series": daily_series(plain, today, 30),
        "wearable_exercise_minutes_7d": wearable,
        "totals": {"sessions": len(plain), "minutes": round(sum(p["minutes"] for p in plain), 1)},
        "disclaimer": DISCLAIMER,
    }


def _wearable_minutes(db: Session, astronaut_id: str, today) -> float | None:
    since = datetime.combine(today - timedelta(days=6), datetime.min.time(), tzinfo=timezone.utc)
    rows = db.execute(select(Measurement).where(
        Measurement.astronaut_id == astronaut_id, Measurement.metric == "exercise_minutes",
        Measurement.source_module != "exercise", Measurement.timestamp >= since)).scalars()
    vals = [r.value for r in rows if r.value is not None]
    if not vals:
        return None
    return round(sum(vals), 1)


def calendar_month(db: Session, astronaut_id: str, year: int, month: int) -> dict:
    from calendar import monthrange
    programs = active_programs(db, astronaut_id)
    personal = programs.get("personalized") or programs.get("general") or {}
    weekdays = set((personal.get("schedule") or {}).get("weekdays") or [0, 1, 2, 3, 4, 5])
    rows = list_sessions(db, astronaut_id, limit=500)
    by_day: dict = {}
    for r in rows:
        if r.status != "completed":
            continue
        d = as_utc(r.started_at).date()
        if d.year == year and d.month == month:
            cell = by_day.setdefault(d.isoformat(), {"minutes": 0.0, "sessions": 0})
            cell["minutes"] = round(cell["minutes"] + float((r.summary or {}).get("minutes") or 0), 1)
            cell["sessions"] += 1
    today = _utcnow().date()
    days = []
    for day in range(1, monthrange(year, month)[1] + 1):
        d = datetime(year, month, day).date()
        cell = by_day.get(d.isoformat(), {"minutes": 0.0, "sessions": 0})
        scheduled = d.weekday() in weekdays
        days.append({**cell, "date": d.isoformat(), "scheduled": scheduled,
                     "missed": scheduled and d < today and cell["sessions"] == 0})
    return {"year": year, "month": month, "astronaut_id": astronaut_id, "days": days}


def health_context(db: Session, astronaut_id: str) -> dict:
    """Stable context block for a future recommendation model. Reads existing daily metrics."""
    ctx = {
        "contract_version": CONTRACT_VERSION, "astronaut_id": astronaut_id,
        "mission_day": None, "sleep_duration_h": None, "fatigue_score": None,
        "resting_heart_rate": None, "heart_rate_variability": None, "oxygen_saturation": None,
        "exercise_minutes_latest": None, "open_warning_count": 0, "open_alert_categories": [],
        "data_as_of": None,
    }
    astro = db.get(Astronaut, astronaut_id)
    if astro:
        mission = db.get(Mission, astro.mission_id)
        if mission and mission.start_date:
            ctx["mission_day"] = (_utcnow().date() - mission.start_date).days + 1
    try:
        from app.intelligence.daily import astronaut_daily
        daily = astronaut_daily(db, astronaut_id, days=14)
        if daily is not None and not daily.empty:
            last = daily.iloc[-1]
            ctx["data_as_of"] = str(last["date"].date()) if hasattr(last["date"], "date") else str(last["date"])[:10]
            mapping = {
                "sleep_duration": "sleep_duration_h", "fatigue_score": "fatigue_score",
                "resting_heart_rate": "resting_heart_rate", "hrv_sdnn": "heart_rate_variability",
                "oxygen_saturation": "oxygen_saturation", "exercise_minutes": "exercise_minutes_latest",
            }
            for src, dest in mapping.items():
                if src not in daily.columns:
                    continue
                try:
                    value = float(last[src])
                except (TypeError, ValueError):
                    continue
                if value != value:  # NaN
                    continue
                ctx[dest] = round(value, 2)
    except Exception:
        log.debug("health context daily frame unavailable", exc_info=True)
    alerts = db.execute(select(Alert).where(Alert.astronaut_id == astronaut_id, Alert.acknowledged.is_(False))).scalars()
    categories = []
    warnings = 0
    for a in alerts:
        if a.category not in categories:
            categories.append(a.category)
        if a.severity == "warning":
            warnings += 1
    ctx["open_warning_count"] = warnings
    ctx["open_alert_categories"] = categories
    return ctx


def recommendation_for(db: Session, astronaut_id: str) -> dict:
    profile = profile_dict(ensure_profile(db, astronaut_id))
    ctx = health_context(db, astronaut_id)
    report = progress_report(db, astronaut_id)
    week = next((g for g in report["goals"] if g["period"] == "week"), None)
    settings = get_settings()
    result = recommend(profile, ctx, None if week is None else week["pct"], _utcnow().weekday(),
                       recommender_url=settings.exercise_recommender_url.strip(),
                       recommender_token=settings.exercise_recommender_token)
    result["astronaut_id"] = astronaut_id
    result["health_context"] = ctx
    return result


def summary_for(db: Session, astronaut_id: str) -> dict:
    report = progress_report(db, astronaut_id)
    week = next((g for g in report["goals"] if g["period"] == "week"), None)
    minutes = next((g for g in report["goals"] if g["period"] == "day" and g["metric"] == "minutes"), None)
    rows = list_sessions(db, astronaut_id, limit=400)
    today = _utcnow().date()
    cutoff = today - timedelta(days=6)
    sessions_7d = sum(1 for r in rows if r.status == "completed" and as_utc(r.started_at).date() >= cutoff)
    return {
        "contract_version": CONTRACT_VERSION,
        "astronaut_id": astronaut_id,
        "as_of": today.isoformat(),
        "sessions_7d": sessions_7d,
        "minutes_today": None if minutes is None else minutes["actual"],
        "streak_days": report["streak_days"],
        "adherence_7d_pct": None if week is None else week["pct"],
        "last_session": session_out(rows[0]) if rows else None,
        "goals": report["goals"],
        "example_only": True,
        "disclaimer": DISCLAIMER,
    }
