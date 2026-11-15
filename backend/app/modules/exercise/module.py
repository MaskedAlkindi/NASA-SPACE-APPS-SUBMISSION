"""Exercise module adapter.

Richer workout data lives in ``app.exercise``. This adapter is the registry
entry so the Modules page and ``POST /measurements`` can accept exercise
minutes through the same contract as the other devices.
"""
from __future__ import annotations

from typing import Any

from app.exercise.catalog import EXERCISES
from app.exercise.tracking import TRACKED_EXERCISES
from app.modules.base import HealthModule
from app.schemas.measurement import DataClass


class ExerciseModule(HealthModule):
    module_id = "exercise"
    version = "1.0.0"
    name = "Exercise & Fitness"
    description = ("Astronaut exercise profiles, example programs, goals, manual logs, and camera rep counting. "
                   "Camera video stays in the browser unless remote processing is explicitly enabled.")
    category = "device"
    data_class = DataClass.real
    supported_metrics = ["exercise_minutes", "active_energy", "heart_rate"]

    def default_config(self) -> dict[str, Any]:
        return {"tracked_exercises": list(TRACKED_EXERCISES), "catalog_size": len(EXERCISES),
                "transmits_video_by_default": False}

    def status(self) -> dict[str, Any]:
        return {"state": "available", "detail": f"{len(TRACKED_EXERCISES)} camera-counted exercises, {len(EXERCISES)} in the catalog"}
