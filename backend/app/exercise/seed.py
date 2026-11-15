"""Demo exercise profiles and a short session history. Idempotent.

Seeded sessions are marked simulated and are not copied into the measurement
table, so they do not double-count the simulator's exercise minutes.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Astronaut, ExerciseProfile, WorkoutSession
from app.exercise import service as exercise

log = logging.getLogger("hmt.exercise")

# callsign-independent ids match the demo crew in ml.datasets.synthetic.
DEMO = {
    "AST-001": {"fitness_level": "intermediate", "focus": "balanced", "limitations": "", "skip": ()},
    "AST-002": {"fitness_level": "intermediate", "focus": "mobility", "limitations": "", "skip": (2, 4, 6)},
    "AST-003": {"fitness_level": "advanced", "focus": "strength", "limitations": "", "skip": ()},
    "AST-004": {"fitness_level": "intermediate", "focus": "cardio", "limitations": "", "skip": (1,)},
    "AST-005": {"fitness_level": "intermediate", "focus": "balanced", "limitations": "", "skip": (3,)},
}


def seed_exercise_demo(db: Session) -> int:
    if db.execute(select(func.count()).select_from(ExerciseProfile)).scalar():
        return 0
    created = 0
    today = datetime.now(timezone.utc).date()
    for aid, spec in DEMO.items():
        if db.get(Astronaut, aid) is None:
            continue
        exercise.save_profile(db, aid, {
            "fitness_level": spec["fitness_level"], "focus": spec["focus"],
            "limitations": spec["limitations"], "equipment": ["bodyweight", "bands", "cycle"],
            "mission_phase": "in_flight",
            "notes": "Example profile created for the demo. Not a real fitness assessment.",
        })
        for offset in (1, 2, 3, 5, 8, 12):
            if offset in spec["skip"]:
                continue
            start = datetime.combine(today - timedelta(days=offset), datetime.min.time(), tzinfo=timezone.utc).replace(hour=8)
            exercise.record_session(db, aid, {
                "source": "manual", "started_at": start, "ended_at": start + timedelta(minutes=45),
                "program_id": f"personalized:{aid}",
                "exercises": [{"exercise_id": "squat", "sets": [{"reps": 10, "rest_s": 60}, {"reps": 10, "rest_s": 60}], "notes": ""},
                              {"exercise_id": "arm_raise", "sets": [{"reps": 12, "rest_s": 30}], "notes": ""}],
                "perceived_exertion": 5, "notes": "Example seeded session, not a real workout.",
                "summary": {}, "client_id": f"seed-{aid}-{offset}", "sync_health": False,
            }, data_class="simulated", emit_alerts=False)
            created += 1
    if db.get(Astronaut, "AST-900") is not None:
        exercise.ensure_profile(db, "AST-900")
    log.info("seeded %d example workout sessions", created)
    return created
