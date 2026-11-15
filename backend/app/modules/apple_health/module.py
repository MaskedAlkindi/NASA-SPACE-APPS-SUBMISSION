"""Apple HealthKit bridge module.

The iOS app reads HealthKit on-device (with per-type user authorisation) and
uploads records. Records may use canonical metric names, or HealthKit
identifiers which are mapped here. Sleep is summarised on-device per night
(``sleep_duration`` in hours), because raw HKCategorySample stages vary by
device and OS version.
"""
from __future__ import annotations

from typing import Any

from app.modules.base import HealthModule, ModuleError
from app.schemas.measurement import DataClass

HK_MAP: dict[str, tuple[str, str, float]] = {
    # identifier: (metric, canonical unit, multiplier from HealthKit unit we request on-device)
    "HKQuantityTypeIdentifierHeartRate": ("heart_rate", "bpm", 1.0),                 # count/min
    "HKQuantityTypeIdentifierRestingHeartRate": ("resting_heart_rate", "bpm", 1.0),
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": ("hrv_sdnn", "ms", 1.0),      # ms
    "HKQuantityTypeIdentifierStepCount": ("steps", "count", 1.0),
    "HKQuantityTypeIdentifierAppleExerciseTime": ("exercise_minutes", "min", 1.0),
    "HKQuantityTypeIdentifierActiveEnergyBurned": ("active_energy", "kcal", 1.0),
    "HKQuantityTypeIdentifierOxygenSaturation": ("oxygen_saturation", "%", 100.0),   # fraction -> %
    "HKQuantityTypeIdentifierBloodPressureSystolic": ("blood_pressure_systolic", "mmHg", 1.0),
    "HKQuantityTypeIdentifierBloodPressureDiastolic": ("blood_pressure_diastolic", "mmHg", 1.0),
    "HKCategoryTypeIdentifierSleepAnalysis": ("sleep_duration", "h", 1.0),            # summarised hours
    "HKQuantityTypeIdentifierBodyTemperature": ("body_temperature", "°C", 1.0),       # degC
    "HKQuantityTypeIdentifierBloodGlucose": ("blood_glucose", "mg/dL", 1.0),          # mg/dL
    "HKQuantityTypeIdentifierBodyMass": ("body_mass", "kg", 1.0),                     # kg
}


class AppleHealthModule(HealthModule):
    module_id = "apple_health"
    version = "1.0.0"
    name = "Apple Health (HealthKit bridge)"
    description = "Receives HealthKit measurements uploaded by the HEALTH-01 iOS app (iPhone + paired Apple Watch)."
    category = "device"
    data_class = DataClass.real
    supported_metrics = sorted({v[0] for v in HK_MAP.values()})

    def default_config(self) -> dict[str, Any]:
        return {"requires_app": "HEALTH-01 iOS 17+", "permissions": "requested per data type on device"}

    def map_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        rec = dict(raw)
        hk = rec.pop("hk_type", None)
        if hk:
            if hk not in HK_MAP:
                raise ModuleError(f"unsupported HealthKit type {hk}")
            metric, unit, mult = HK_MAP[hk]
            rec["metric"], rec["unit"] = metric, unit
            if rec.get("value") is not None:
                rec["value"] = float(rec["value"]) * mult
        rec.setdefault("source_device", "Apple Health")
        rec.setdefault("quality", "good")
        return rec
