"""Habitat environment module (cabin atmosphere + radiation).

Accepts readings from any environmental sensor feed (real ECLSS telemetry in a
future integration; the simulator in this prototype). Readings are habitat-wide
so ``astronaut_id`` is not stored.
"""
from __future__ import annotations

from typing import Any

from app.modules.base import HealthModule
from app.schemas.measurement import DataClass

# Demo thresholds only - configure to the mission's standard (e.g. NASA-STD-3001 Vol. 2).
DEFAULT_LIMITS = {
    "cabin_co2": {"caution": 3.0, "warning": 4.0, "unit": "mmHg"},
    "cabin_temperature": {"low": 18.0, "high": 27.0, "unit": "°C"},
    "cabin_humidity": {"low": 25.0, "high": 70.0, "unit": "%"},
    "cabin_pressure": {"low": 97.0, "high": 104.0, "unit": "kPa"},
    "radiation_dose_rate": {"caution": 60.0, "warning": 150.0, "unit": "µGy/h"},
}


class EnvironmentModule(HealthModule):
    module_id = "environment"
    version = "1.0.0"
    name = "Habitat environment"
    description = "Cabin temperature, humidity, CO₂, pressure and radiation dose rate."
    category = "environment"
    data_class = DataClass.real
    supported_metrics = list(DEFAULT_LIMITS)

    def default_config(self) -> dict[str, Any]:
        return {"limits": DEFAULT_LIMITS, "limits_note": "demo thresholds - not a flight standard"}

    def map_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        rec = dict(raw)
        rec.pop("astronaut_id", None)
        rec.setdefault("source_device", "habitat-sensor")
        return rec
