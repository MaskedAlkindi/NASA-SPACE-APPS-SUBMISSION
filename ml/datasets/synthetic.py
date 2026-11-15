"""Synthetic astronaut data generator.

EVERYTHING PRODUCED HERE IS SIMULATED. It is used for (a) demo data, (b) the
live mission simulator and (c) training/evaluating the prototype ML models,
because no public NASA dataset provides daily wearable + questionnaire data
for astronauts with outcome labels.

The generative model is deliberately simple and documented so that model
metrics computed on it are understood as *simulation* metrics only:

* Personal baselines differ per crew member (resting HR, HRV, sleep need...).
* Sleep debt and circadian misalignment (variability of sleep midpoint) raise
  fatigue and resting HR, lower HRV and slow reaction time - directionally
  consistent with sleep/circadian literature, but the coefficients are made up.
* Optional "episodes" inject multi-day physiological deviations (labelled), used
  to evaluate the anomaly detector.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class CrewProfile:
    astronaut_id: str
    callsign: str
    name: str
    role: str
    rhr_base: float          # resting heart rate, bpm
    hrv_base: float          # SDNN, ms
    sleep_need: float        # hours
    midpoint_base: float     # sleep midpoint, hours after midnight (station time)
    steps_base: float        # steps/day
    exercise_base: float     # minutes/day (ISS-style ~2h exercise protocol)
    sbp_base: float          # systolic mmHg
    dbp_base: float          # diastolic mmHg
    rt_base: float           # PVT-style mean reaction time, ms
    stress_sensitivity: float = 1.0
    temp_base: float = 37.4  # in-flight resting body temperature, degC (core temp ~1 degC higher in microgravity:
                             # NASA "Human Adaptation to Spaceflight: The Role of Food and Nutrition", p.21)
    glucose_base: float = 88.0  # fasting blood glucose, mg/dL
    mass_start: float = 75.0    # body mass at mission start, kg


DEFAULT_CREW: list[CrewProfile] = [
    CrewProfile("AST-001", "HAJID", "Hajid Alkindi", "Commander",
                58, 52, 7.4, 3.2, 6200, 110, 118, 76, 265, 0.9, 37.3, 86, 64.0),
    CrewProfile("AST-002", "OSAMA", "Osama Al Adawani", "Flight Engineer / Medical Officer",
                62, 44, 7.8, 3.6, 5600, 95, 122, 79, 280, 1.1, 37.5, 92, 78.0),
    CrewProfile("AST-003", "HAMOOD", "Hamood Almahrouqi", "Mission Specialist",
                55, 61, 7.2, 2.9, 7100, 120, 112, 72, 255, 1.0, 37.4, 84, 61.0),
    CrewProfile("AST-004", "HAITHAM", "Al Haitham Al Obaidani", "Flight Engineer",
                64, 39, 7.6, 3.4, 5100, 100, 126, 82, 290, 1.2, 37.4, 89, 84.0),
    CrewProfile("AST-005", "MOHMMED", "Mohmmed Alwahabi", "Science Officer / Astrophotographer",
                60, 48, 7.5, 3.8, 6600, 105, 119, 77, 270, 1.0, 37.4, 87, 70.0),
]

# Scenario effects that the simulator / seed can apply to a range of days.
SCENARIOS = {
    "nominal": "No injected disturbance.",
    "sleep_disruption": "Shortened, shifted sleep (e.g. schedule shift / noise) for several nights.",
    "fatigue_buildup": "High workload with gradual sleep restriction over a week.",
    "cardio_anomaly": "Elevated resting HR and suppressed HRV without obvious behavioural cause.",
    "co2_scrubber_fault": "Cabin CO2 partial pressure rises (environmental scenario).",
    "radiation_event": "Simulated solar particle event raising dose rate for ~1 day.",
    "illness_like": "Combined HR rise, HRV drop, sleep loss and fatigue (illness-like pattern).",
}


@dataclass
class Episode:
    kind: str
    start_day: int
    length: int
    severity: float = 1.0
    astronaut_id: str | None = None   # None = everyone / environment


@dataclass
class SimConfig:
    days: int = 45
    seed: int = 7
    start: date | None = None
    episodes: list[Episode] = field(default_factory=list)


def _clip(x, lo, hi):
    return float(np.clip(x, lo, hi))


def episode_effects(day: int, aid: str, episodes: list[Episode]) -> dict[str, float]:
    """Return additive / multiplicative effects active on a given mission day."""
    eff = {"sleep": 0.0, "midpoint": 0.0, "rhr": 0.0, "hrv_mult": 1.0, "workload": 0.0,
           "fatigue": 0.0, "co2": 0.0, "radiation_mult": 1.0, "exercise": 0.0, "temp": 0.0, "glucose": 0.0}
    for ep in episodes:
        if ep.astronaut_id not in (None, aid):
            continue
        if not (ep.start_day <= day < ep.start_day + ep.length):
            continue
        k = ep.severity
        progress = (day - ep.start_day + 1) / ep.length
        if ep.kind == "sleep_disruption":
            eff["sleep"] -= 1.8 * k
            eff["midpoint"] += 2.0 * k
        elif ep.kind == "fatigue_buildup":
            eff["sleep"] -= 1.4 * k * progress
            eff["workload"] += 25 * k
            eff["exercise"] -= 30 * k * progress
        elif ep.kind == "cardio_anomaly":
            eff["rhr"] += 12 * k
            eff["hrv_mult"] *= (1 - 0.35 * k)
        elif ep.kind == "illness_like":
            eff["rhr"] += 9 * k
            eff["hrv_mult"] *= (1 - 0.3 * k)
            eff["sleep"] -= 1.0 * k
            eff["fatigue"] += 1.5 * k
            eff["exercise"] -= 50 * k
            eff["temp"] += 0.9 * k * min(1.0, progress * 2)
            eff["glucose"] += 12 * k
        elif ep.kind == "co2_scrubber_fault":
            eff["co2"] += 2.8 * k * min(1.0, progress * 2)
        elif ep.kind == "radiation_event":
            eff["radiation_mult"] *= 1 + 9 * k
    return eff


def generate_daily(profiles: list[CrewProfile] | None = None, cfg: SimConfig | None = None) -> pd.DataFrame:
    """Generate one row per astronaut per mission day (simulated)."""
    profiles = profiles or DEFAULT_CREW
    cfg = cfg or SimConfig()
    rng = np.random.default_rng(cfg.seed)
    start = cfg.start or (datetime.now(timezone.utc).date() - timedelta(days=cfg.days - 1))
    rows = []
    for p in profiles:
        sleep_hist: list[float] = []
        mid_hist: list[float] = []
        prev_fatigue = 3.0
        prev_ex = p.exercise_base
        for d in range(cfg.days):
            eff = episode_effects(d, p.astronaut_id, cfg.episodes)
            day = start + timedelta(days=d)
            weekend_like = (d % 7) in (5, 6)   # lighter schedule days
            workload = _clip(rng.normal(55 if not weekend_like else 38, 9) + eff["workload"], 5, 100)
            sleep = _clip(rng.normal(p.sleep_need - 0.35 - 0.012 * (workload - 50), 0.45) + eff["sleep"], 3.0, 10.0)
            midpoint = rng.normal(p.midpoint_base, 0.35) + eff["midpoint"]
            sleep_hist.append(sleep)
            mid_hist.append(midpoint)
            debt3 = float(np.sum(np.maximum(0.0, p.sleep_need - np.array(sleep_hist[-3:]))))
            mid_sd3 = float(np.std(mid_hist[-3:])) if len(mid_hist) >= 2 else 0.0
            efficiency = _clip(rng.normal(88 - 2.5 * mid_sd3 - 1.5 * max(0, eff["midpoint"]), 3), 55, 99)
            exercise = _clip(rng.normal(p.exercise_base, 15) + eff["exercise"], 0, 180)
            steps = _clip(rng.normal(p.steps_base + 18 * (exercise - p.exercise_base), 700), 300, 20000)
            rhr = p.rhr_base + 0.9 * debt3 + 0.6 * mid_sd3 + rng.normal(0, 1.4) + eff["rhr"]
            hrv = max(8.0, (p.hrv_base - 2.2 * debt3 - 1.5 * mid_sd3 + rng.normal(0, 3.5)) * eff["hrv_mult"])
            sbp = p.sbp_base + 0.4 * debt3 + rng.normal(0, 4) + 0.3 * eff["rhr"]
            dbp = p.dbp_base + 0.3 * debt3 + rng.normal(0, 3) + 0.2 * eff["rhr"]
            # Fatigue (Samn-Perelli 1-7). Simulation ground truth (coefficients invented).
            fatigue_true = (1.6 + 0.55 * debt3 + 0.45 * mid_sd3 + 0.022 * workload
                            + 0.006 * max(0, p.exercise_base - prev_ex) * 3
                            + 0.25 * (prev_fatigue - 3) + 0.25 * max(0, p.sleep_need - sleep)
                            + eff["fatigue"] + rng.normal(0, 0.45) * p.stress_sensitivity)
            fatigue = _clip(round(fatigue_true * 2) / 2, 1, 7)
            stress = _clip(rng.normal(3 + 0.05 * (workload - 50) * p.stress_sensitivity + 0.4 * debt3, 1.0), 1, 10)
            mood = _clip(round(rng.normal(4.1 - 0.25 * debt3 - 0.15 * (stress - 3), 0.5)), 1, 5)
            rt = p.rt_base + 9 * debt3 + 6 * mid_sd3 + 10 * max(0, fatigue - 3) + rng.normal(0, 9)
            temp = p.temp_base + rng.normal(0, 0.12) + eff["temp"]
            glucose = p.glucose_base + rng.normal(0, 5) + eff["glucose"] + 1.5 * max(0, stress - 5)
            # ~2.4% body-mass loss per 100 days on average (NASA nutrition report, p.22)
            mass = p.mass_start * (1 - 0.024 * d / 100) + rng.normal(0, 0.25)
            active = [ep.kind for ep in cfg.episodes
                      if ep.astronaut_id in (None, p.astronaut_id)
                      and ep.start_day <= d < ep.start_day + ep.length
                      and ep.kind in ("cardio_anomaly", "illness_like", "sleep_disruption", "fatigue_buildup")]
            rows.append({
                "astronaut_id": p.astronaut_id, "mission_day": d, "date": day,
                "sleep_duration": round(sleep, 2), "sleep_midpoint": round(midpoint, 2),
                "sleep_efficiency": round(efficiency, 1),
                "resting_heart_rate": round(rhr, 1), "hrv_sdnn": round(hrv, 1),
                "steps": int(steps), "exercise_minutes": round(exercise, 0),
                "blood_pressure_systolic": round(sbp, 0), "blood_pressure_diastolic": round(dbp, 0),
                "workload_tlx": round(workload, 0), "fatigue_score": fatigue, "stress_score": round(stress, 0),
                "mood_score": mood, "reaction_time": round(rt, 0),
                "body_temperature": round(temp, 2), "blood_glucose": round(glucose, 0), "body_mass": round(mass, 1),
                "label_anomaly": int(bool(set(active) & {"cardio_anomaly", "illness_like"})),
                "label_episode": ",".join(active),
            })
            prev_fatigue = fatigue
            prev_ex = exercise
    return pd.DataFrame(rows)


def intraday_heart_rate(rhr: float, sleep_duration: float, midpoint: float, exercise_minutes: float,
                        rng: np.random.Generator, hours: range = range(24)) -> list[tuple[int, float]]:
    """Hourly heart-rate samples for one day derived from that day's daily values."""
    sleep_start = (midpoint - sleep_duration / 2) % 24
    out = []
    ex_hour = 15  # scheduled exercise block (station time)
    for h in hours:
        asleep = ((h - sleep_start) % 24) < sleep_duration
        hr = rhr + (rng.normal(-2, 1.5) if asleep else rng.normal(14, 5))
        if h in (ex_hour, ex_hour + 1) and exercise_minutes > 20:
            hr += 35 * min(1.0, exercise_minutes / 120) + rng.normal(0, 6)
        out.append((h, round(max(38.0, hr), 0)))
    return out


def environment_reading(hour_index: int, rng: np.random.Generator, co2_offset: float = 0.0,
                        radiation_mult: float = 1.0) -> dict[str, float]:
    """One simulated cabin environment sample (station module)."""
    return {
        "cabin_temperature": round(22.2 + 0.6 * np.sin(hour_index / 24 * 2 * np.pi) + rng.normal(0, 0.15), 2),
        "cabin_humidity": round(_clip(46 + rng.normal(0, 2.0), 25, 75), 1),
        "cabin_co2": round(max(0.5, 2.3 + 0.3 * np.sin(hour_index / 12 * np.pi) + co2_offset + rng.normal(0, 0.12)), 2),
        "cabin_pressure": round(101.3 + rng.normal(0, 0.15), 2),
        "radiation_dose_rate": round(max(0.0, rng.normal(18.5, 1.8) * radiation_mult), 2),  # µGy/h
    }


def default_seed_episodes(days: int) -> list[Episode]:
    """Episodes baked into the demo history so the dashboard has something to explain."""
    return [
        Episode("sleep_disruption", max(0, days - 18), 3, 1.0, "AST-002"),
        Episode("cardio_anomaly", max(0, days - 3), 3, 1.0, "AST-004"),
        Episode("fatigue_buildup", max(0, days - 8), 8, 0.8, "AST-002"),
        Episode("co2_scrubber_fault", max(0, days - 2), 2, 0.6, None),
    ]
