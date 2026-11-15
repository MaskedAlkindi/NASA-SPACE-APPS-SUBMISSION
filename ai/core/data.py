"""The health data interface models read from.

Models never touch the database. They receive a `HealthDataView` for exactly one
astronaut. The backend implements it over its measurement store; tests and training
use `FrameHealthDataView`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import pandas as pd

from ai.core.types import FeatureSpec


class HealthDataView(Protocol):
    astronaut_id: str

    def daily(self, metrics: list[str], days: int = 60) -> pd.DataFrame:
        """One row per day (column `date`), one column per canonical metric; NaN where missing."""

    def series(self, metric: str, days: int = 7) -> pd.DataFrame:
        """Raw samples: columns `timestamp` (UTC), `value`."""

    def last_seen(self, metric: str) -> datetime | None:
        """Timestamp of the newest sample, for staleness checks."""

    def unit(self, metric: str) -> str | None:
        """Canonical unit for a metric (None if unknown)."""

    def profile(self) -> dict[str, Any]:
        """Non-identifying context: mission day, role, data class. Never names."""

    def exercise_sessions(self, days: int = 14) -> list[dict]:
        """Exercise session summaries following contracts/exercise_session_summary.v1."""


def check_inputs(view: HealthDataView, specs: list[FeatureSpec], now: datetime | None = None) -> dict:
    """Unit compatibility, availability and staleness for a model's inputs."""
    now = now or datetime.now(timezone.utc)
    missing, stale, unit_mismatch, available = [], [], [], []
    for s in specs:
        if s.kind == "profile":
            continue
        u = view.unit(s.metric)
        if u is not None and u != s.unit:
            unit_mismatch.append({"metric": s.metric, "expected": s.unit, "found": u})
            continue
        ts = view.last_seen(s.metric)
        if ts is None:
            if s.required:
                missing.append(s.metric)
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if now - ts > timedelta(days=s.max_staleness_days):
            stale.append({"metric": s.metric, "last_seen": ts.isoformat()})
        else:
            available.append(s.metric)
    required = [s.metric for s in specs if s.required and s.kind != "profile"]
    ok = not unit_mismatch and all(m in available for m in required)
    return {"ok": ok, "available": available, "missing": missing, "stale": stale, "unit_mismatch": unit_mismatch,
            "coverage": round(len([m for m in required if m in available]) / len(required), 2) if required else 1.0}


class FrameHealthDataView:
    """In-memory view over a daily DataFrame (tests, offline evaluation, desktop use)."""

    def __init__(self, astronaut_id: str, daily: pd.DataFrame, units: dict[str, str],
                 samples: dict[str, pd.DataFrame] | None = None, profile: dict | None = None,
                 sessions: list[dict] | None = None, now: datetime | None = None):
        self.astronaut_id = astronaut_id
        self._daily = daily.copy()
        self._daily["date"] = pd.to_datetime(self._daily["date"])
        self._units = units
        self._samples = samples or {}
        self._profile = profile or {}
        self._sessions = sessions or []
        self._now = now

    def daily(self, metrics, days=60):
        df = self._daily.sort_values("date").tail(days)
        out = pd.DataFrame({"date": df["date"].values})
        for m in metrics:
            out[m] = df[m].values if m in df.columns else float("nan")
        return out

    def series(self, metric, days=7):
        return self._samples.get(metric, pd.DataFrame(columns=["timestamp", "value"]))

    @property
    def now(self):
        return self._now

    def last_seen(self, metric):
        if metric in self._samples and not self._samples[metric].empty:
            return pd.Timestamp(self._samples[metric]["timestamp"].max()).to_pydatetime()
        if metric in self._daily.columns and self._daily[metric].notna().any():
            d = self._daily.loc[self._daily[metric].notna(), "date"].max()
            return (pd.Timestamp(d) + pd.Timedelta(hours=12)).tz_localize("UTC").to_pydatetime()
        return None

    def unit(self, metric):
        return self._units.get(metric)

    def profile(self):
        return dict(self._profile)

    def exercise_sessions(self, days=14):
        return list(self._sessions)
