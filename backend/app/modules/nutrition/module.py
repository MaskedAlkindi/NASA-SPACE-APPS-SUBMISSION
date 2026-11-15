"""Registry entry for the food log. The rows themselves live in app.nutrition."""
from __future__ import annotations

from typing import Any

from app.modules.base import HealthModule
from app.nutrition.catalog import FOODS, MARKS
from app.schemas.measurement import DataClass


class NutritionModule(HealthModule):
    module_id = "nutrition"
    version = "1.0.0"
    name = "Nutrition"
    description = (
        "Meal log, fluid, and body mass for one crew member. "
        "Daily rings use example marks so a short day is visible. Not a flight menu."
    )
    category = "device"
    data_class = DataClass.real
    supported_metrics = ["body_mass", "energy_kcal", "fluid_ml"]
    accepts_ingest = False

    def default_config(self) -> dict[str, Any]:
        return {"example_foods": len(FOODS), "marks": [m["key"] for m in MARKS]}

    def status(self) -> dict[str, Any]:
        return {"state": "available", "detail": "meal log and body mass, with example daily marks"}
