"""Backend implementation of ai.core.data.HealthDataView for ONE astronaut.

Reads only that astronaut's measurements (profile isolation), reports canonical units from
the metric catalog, and never substitutes simulated values for missing ones: whatever is
stored (real, research or simulated) is returned with its data class, nothing is filled in.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai_engine.db_models import AiExerciseSession
from app.database import models as dbm
from app.database.models import Astronaut, Measurement
from app.intelligence.daily import daily_frame, latest_timestamp, load_measurements
from app.schemas.metrics import METRICS


class BackendHealthDataView:
    def __init__(self, db: Session, astronaut_id: str):
        self.db = db
        self.astronaut_id = astronaut_id
        self._latest = latest_timestamp(db, astronaut_id)
        self._daily_cache: dict[int, pd.DataFrame] = {}

    def _now_anchor(self) -> datetime:
        ts = self._latest or datetime.now(timezone.utc)
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

    def daily(self, metrics, days=60):
        if days not in self._daily_cache:
            raw = load_measurements(self.db, self.astronaut_id, since=self._now_anchor() - timedelta(days=days))
            self._daily_cache[days] = daily_frame(raw)
        df = self._daily_cache[days]
        out = pd.DataFrame({"date": pd.to_datetime(df["date"]) if "date" in df else pd.Series(dtype="datetime64[ns]")})
        for m in metrics:
            out[m] = df[m].values if m in df.columns else float("nan")
        return out

    def series(self, metric, days=7):
        q = (select(Measurement.timestamp, Measurement.value, Measurement.value_json)
             .where(Measurement.astronaut_id == self.astronaut_id, Measurement.metric == metric,
                    Measurement.timestamp >= self._now_anchor() - timedelta(days=days))
             .order_by(Measurement.timestamp))
        rows = self.db.execute(q).all()
        return pd.DataFrame(rows, columns=["timestamp", "value", "value_json"])

    def last_seen(self, metric):
        ts = self.db.execute(select(Measurement.timestamp).where(
            Measurement.astronaut_id == self.astronaut_id, Measurement.metric == metric)
            .order_by(Measurement.timestamp.desc()).limit(1)).scalar()
        if ts is not None and ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts

    def unit(self, metric):
        m = METRICS.get(metric)
        return m.unit if m else None

    def profile(self) -> dict[str, Any]:
        a = self.db.get(Astronaut, self.astronaut_id)
        return {"astronaut_id": self.astronaut_id, "role": a.role if a else None, "data_class": a.data_class if a else None}

    def exercise_sessions(self, days=14):
        since = self._now_anchor() - timedelta(days=days)
        out = [r.payload for r in self.db.execute(select(AiExerciseSession).where(
            AiExerciseSession.astronaut_id == self.astronaut_id, AiExerciseSession.started_at >= since)).scalars()]
        # Read-only adapter to the exercise module's table, if that module is installed.
        ws = getattr(dbm, "WorkoutSession", None)
        if ws is not None:
            for w in self.db.execute(select(ws).where(ws.astronaut_id == self.astronaut_id, ws.started_at >= since)).scalars():
                dur = None
                if w.ended_at and w.started_at:
                    dur = round((w.ended_at - w.started_at).total_seconds() / 60, 1)
                out.append({"schema_version": "exercise_session_summary.v1", "session_id": f"workout-{w.id}",
                            "astronaut_id": w.astronaut_id, "started_at": w.started_at.isoformat(),
                            "ended_at": w.ended_at.isoformat() if w.ended_at else None,
                            "activity_type": (w.summary or {}).get("kind", "unspecified") if isinstance(w.summary, dict) else "unspecified",
                            "planned": bool(w.program_id), "completed": w.status == "completed", "duration_min": dur,
                            "intensity_rpe": w.perceived_exertion, "avg_heart_rate": w.heart_rate_avg,
                            "source_module": "exercise.workout_sessions", "data_class": w.data_class})
        return out
