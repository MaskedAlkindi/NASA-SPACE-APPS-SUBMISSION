"""Catalog of supported metrics: canonical name, unit, domain, valid range, daily aggregation."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricDef:
    name: str
    label: str
    unit: str
    domain: str
    min: float
    max: float
    daily: str            # mean | sum | min | max | last
    per_astronaut: bool = True
    description: str = ""


_DEFS = [
    # A. Cardiovascular
    MetricDef("heart_rate", "Heart rate", "bpm", "cardiovascular", 25, 230, "mean"),
    MetricDef("resting_heart_rate", "Resting heart rate", "bpm", "cardiovascular", 25, 140, "mean"),
    MetricDef("hrv_sdnn", "Heart-rate variability (SDNN)", "ms", "cardiovascular", 1, 300, "mean"),
    MetricDef("hrv_rmssd", "Heart-rate variability (RMSSD)", "ms", "cardiovascular", 1, 300, "mean",
              description="Health Connect reports RMSSD; not interchangeable with SDNN"),
    MetricDef("blood_pressure_systolic", "Systolic blood pressure", "mmHg", "cardiovascular", 60, 250, "mean"),
    MetricDef("blood_pressure_diastolic", "Diastolic blood pressure", "mmHg", "cardiovascular", 30, 160, "mean"),
    MetricDef("oxygen_saturation", "Blood oxygen saturation", "%", "cardiovascular", 50, 100, "mean"),
    # Vitals & metabolism (indicators named in the challenge brief)
    MetricDef("body_temperature", "Body temperature", "°C", "vitals", 30, 45, "mean",
              description="Compared with the astronaut's own in-flight baseline (core temperature runs ~1 °C higher in microgravity)"),
    MetricDef("blood_glucose", "Blood glucose", "mg/dL", "vitals", 20, 600, "mean", description="Fasting / morning value"),
    MetricDef("body_mass", "Body mass", "kg", "vitals", 20, 300, "mean"),
    MetricDef("fasting_insulin", "Fasting insulin (lab)", "µIU/mL", "vitals", 0.5, 300, "last",
              description="Laboratory value; enables HOMA-IR in the glucose model"),
    # B. Sleep & fatigue
    MetricDef("sleep_duration", "Sleep duration", "h", "sleep", 0, 16, "sum", description="Total sleep for the night ending on this date"),
    MetricDef("sleep_efficiency", "Sleep efficiency", "%", "sleep", 0, 100, "mean"),
    MetricDef("sleep_midpoint", "Sleep midpoint", "h", "sleep", -12, 36, "mean", description="Hours after local midnight"),
    MetricDef("fatigue_score", "Fatigue (Samn-Perelli)", "score 1-7", "sleep", 1, 7, "mean"),
    # C. Activity
    MetricDef("steps", "Steps", "count", "activity", 0, 100000, "sum"),
    MetricDef("exercise_minutes", "Exercise", "min", "activity", 0, 600, "sum"),
    MetricDef("active_energy", "Active energy", "kcal", "activity", 0, 10000, "sum"),
    # D. Environment (habitat; astronaut_id null)
    MetricDef("cabin_temperature", "Cabin temperature", "°C", "environment", 0, 50, "mean", per_astronaut=False),
    MetricDef("cabin_humidity", "Cabin relative humidity", "%", "environment", 0, 100, "mean", per_astronaut=False),
    MetricDef("cabin_co2", "Cabin CO₂ partial pressure", "mmHg", "environment", 0, 30, "mean", per_astronaut=False),
    MetricDef("cabin_pressure", "Cabin total pressure", "kPa", "environment", 30, 120, "mean", per_astronaut=False),
    MetricDef("radiation_dose_rate", "Radiation dose rate", "µGy/h", "environment", 0, 100000, "mean", per_astronaut=False),
    # E. Psychological wellbeing
    MetricDef("mood_score", "Mood", "score 1-5", "wellbeing", 1, 5, "mean"),
    MetricDef("stress_score", "Perceived stress", "score 1-10", "wellbeing", 1, 10, "mean"),
    MetricDef("workload_tlx", "Workload (NASA-TLX)", "score 0-100", "wellbeing", 0, 100, "mean"),
    MetricDef("reaction_time", "Reaction time (PVT-style)", "ms", "wellbeing", 100, 2000, "mean"),
]

METRICS: dict[str, MetricDef] = {m.name: m for m in _DEFS}
DOMAINS = sorted({m.domain for m in _DEFS})
