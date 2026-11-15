"""Mission simulator module - produces clearly labelled SIMULATED measurements.

Used for (1) seeding demo history and (2) live, accelerated mission replays with
injected scenarios (sleep disruption, fatigue, cardio anomaly, CO2 fault...).
It emits normalised records to a sink callback and knows nothing about the
database, alerts or other modules.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, time, timedelta, timezone
from typing import Any

import numpy as np

from app.modules.base import HealthModule
from app.schemas.measurement import DataClass
from ml.datasets.synthetic import (DEFAULT_CREW, SCENARIOS, Episode, SimConfig, default_seed_episodes,
                                   environment_reading, episode_effects, generate_daily, intraday_heart_rate)

log = logging.getLogger("hmt.sim")

UNITS = {"sleep_duration": "h", "sleep_efficiency": "%", "sleep_midpoint": "h", "resting_heart_rate": "bpm",
         "hrv_sdnn": "ms", "steps": "count", "exercise_minutes": "min", "blood_pressure_systolic": "mmHg",
         "blood_pressure_diastolic": "mmHg", "workload_tlx": "score 0-100", "fatigue_score": "score 1-7",
         "stress_score": "score 1-10", "mood_score": "score 1-5", "reaction_time": "ms", "heart_rate": "bpm",
         "cabin_temperature": "°C", "cabin_humidity": "%", "cabin_co2": "mmHg", "cabin_pressure": "kPa",
         "radiation_dose_rate": "µGy/h", "body_temperature": "°C", "blood_glucose": "mg/dL", "body_mass": "kg"}
# station hour at which each daily metric is reported
DAILY_SCHEDULE = {7: ["sleep_duration", "sleep_efficiency", "sleep_midpoint", "resting_heart_rate", "hrv_sdnn",
                      "body_temperature", "blood_glucose", "body_mass"],
                  8: ["blood_pressure_systolic", "blood_pressure_diastolic"],
                  9: ["reaction_time"],
                  20: ["workload_tlx", "fatigue_score", "stress_score", "mood_score"],
                  22: ["steps", "exercise_minutes"]}
DEVICE = {"heart_rate": "SimWatch-HR", "hrv_sdnn": "SimWatch-HR", "resting_heart_rate": "SimWatch-HR",
          "sleep_duration": "SimWatch-Sleep", "sleep_efficiency": "SimWatch-Sleep", "sleep_midpoint": "SimWatch-Sleep",
          "steps": "SimWatch-Motion", "exercise_minutes": "SimWatch-Motion",
          "blood_pressure_systolic": "SimCuff", "blood_pressure_diastolic": "SimCuff",
          "body_temperature": "SimThermometer", "blood_glucose": "SimGlucometer", "body_mass": "SimBodyMassDevice"}


def _rec(aid, metric, value, ts, device=None) -> dict[str, Any]:
    return {"astronaut_id": aid, "metric": metric, "value": float(value), "unit": UNITS[metric],
            "timestamp": ts.isoformat(), "source_device": device or DEVICE.get(metric, "self-report-sim"),
            "quality": "good", "data_class": "simulated"}


def daily_rows_to_records(df, hours: list[int] | None = None) -> list[dict]:
    out = []
    for r in df.to_dict("records"):
        day = r["date"]
        for hour, metrics in DAILY_SCHEDULE.items():
            if hours is not None and hour not in hours:
                continue
            ts = datetime.combine(day, time(hour, 0), tzinfo=timezone.utc)
            out += [_rec(r["astronaut_id"], m, r[m], ts) for m in metrics]
    return out


class SimulationModule(HealthModule):
    module_id = "simulation"
    version = "1.0.0"
    name = "Mission simulator"
    description = "Synthetic crew wearables, check-ins and habitat sensors with scenario injection. ALL DATA SIMULATED."
    category = "simulation"
    data_class = DataClass.simulated
    supported_metrics = sorted(UNITS)

    def __init__(self, config=None):
        super().__init__(config)
        self._task: asyncio.Task | None = None
        self.state: dict[str, Any] = {"running": False}

    def default_config(self) -> dict[str, Any]:
        return {"scenarios": SCENARIOS, "crew": [p.astronaut_id for p in DEFAULT_CREW]}

    def status(self) -> dict[str, Any]:
        return {"state": "running" if self.state.get("running") else "available",
                "detail": self.state.get("scenario", "idle")}

    # ---- seed history ----------------------------------------------------
    def seed_records(self, days: int, end_date=None, seed: int = 7) -> list[dict]:
        end_date = end_date or datetime.now(timezone.utc).date()
        start = end_date - timedelta(days=days - 1)
        eps = default_seed_episodes(days)
        df = generate_daily(DEFAULT_CREW, SimConfig(days=days, seed=seed, start=start, episodes=eps))
        recs = daily_rows_to_records(df)
        rng = np.random.default_rng(seed)
        recent = df[df["mission_day"] >= days - 14]
        for r in recent.to_dict("records"):
            for h, hr in intraday_heart_rate(r["resting_heart_rate"], r["sleep_duration"], r["sleep_midpoint"],
                                             r["exercise_minutes"], rng):
                ts = datetime.combine(r["date"], time(h, 0), tzinfo=timezone.utc)
                recs.append(_rec(r["astronaut_id"], "heart_rate", hr, ts))
        env_start = days - 7
        for d in range(env_start, days):
            eff = episode_effects(d, "", eps)
            for h in range(24):
                ts = datetime.combine(start + timedelta(days=d), time(h, 0), tzinfo=timezone.utc)
                for m, v in environment_reading(d * 24 + h, rng, eff["co2"], eff["radiation_mult"]).items():
                    recs.append(_rec(None, m, v, ts, "SimECLSS-ModuleA"))
        return recs

    # ---- live replay -----------------------------------------------------
    def start(self, sink: Callable[[list[dict]], Awaitable[None]], start_at: datetime, scenario: str,
              astronaut_id: str | None, days: int, severity: float, tick_seconds: float) -> dict:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario {scenario}")
        self.stop()
        crew = DEFAULT_CREW
        env_kinds = {"co2_scrubber_fault", "radiation_event"}
        target = None if scenario in env_kinds else (astronaut_id or crew[0].astronaut_id)
        # health scenarios stay active until the run ends, so the final model results show the scenario
        length = {"radiation_event": 1}.get(scenario, max(1, days))
        episodes = [] if scenario == "nominal" else [Episode(scenario, 1, length, severity, target)]
        start_at = start_at.replace(minute=0, second=0, microsecond=0)
        seed = int(start_at.timestamp()) % 100_000
        daily = generate_daily(crew, SimConfig(days=days + 1, seed=seed, start=start_at.date(), episodes=episodes))
        self.state = {"running": True, "scenario": scenario, "astronaut_id": target, "days": days,
                      "started_wall": datetime.now(timezone.utc).isoformat(),
                      "severity": severity, "sim_time": start_at.isoformat(), "start_at": start_at.isoformat(),
                      "tick_seconds": tick_seconds, "ticks": 0, "records_emitted": 0}
        self._task = asyncio.create_task(self._run(sink, start_at, daily, episodes, days, tick_seconds, seed))
        return dict(self.state)

    async def _run(self, sink, start_at, daily, episodes, days, tick_seconds, seed):
        rng = np.random.default_rng(seed)
        total_hours = days * 24
        try:
            for i in range(1, total_hours + 1):
                ts = start_at + timedelta(hours=i)
                sim_day = (ts.date() - start_at.date()).days
                recs: list[dict] = []
                rows = daily[daily["date"] == ts.date()]
                for r in rows.to_dict("records"):
                    recs.append(_rec(r["astronaut_id"], "heart_rate",
                                     intraday_heart_rate(r["resting_heart_rate"], r["sleep_duration"],
                                                         r["sleep_midpoint"], r["exercise_minutes"], rng,
                                                         range(ts.hour, ts.hour + 1))[0][1], ts))
                    if ts.hour in DAILY_SCHEDULE:
                        recs += [_rec(r["astronaut_id"], m, r[m], ts) for m in DAILY_SCHEDULE[ts.hour]]
                eff = episode_effects(sim_day, "", episodes)
                for m, v in environment_reading(i, rng, eff["co2"], eff["radiation_mult"]).items():
                    recs.append(_rec(None, m, v, ts, "SimECLSS-ModuleA"))
                await sink(recs)
                self.state.update(sim_time=ts.isoformat(), ticks=i, records_emitted=self.state["records_emitted"] + len(recs),
                                  progress=round(i / total_hours, 3))
                await asyncio.sleep(tick_seconds)
            self.state["running"] = False
            self.state["finished"] = True
        except asyncio.CancelledError:
            self.state["running"] = False
            raise
        except Exception as e:  # keep the API alive if the simulator crashes
            log.exception("simulator failed")
            self.state.update(running=False, error=str(e))

    def stop(self) -> dict:
        if self._task and not self._task.done():
            self._task.cancel()
        self.state["running"] = False
        return dict(self.state)
