"""Android Health Connect bridge module.

Health Connect exposes HRV as RMSSD (HeartRateVariabilityRmssdRecord), which is
stored as ``hrv_rmssd`` and is NOT merged with Apple's SDNN.
"""
from __future__ import annotations

from typing import Any

from app.modules.base import HealthModule, ModuleError
from app.schemas.measurement import DataClass

HC_MAP: dict[str, tuple[str, str]] = {
    "HeartRateRecord": ("heart_rate", "bpm"),
    "RestingHeartRateRecord": ("resting_heart_rate", "bpm"),
    "HeartRateVariabilityRmssdRecord": ("hrv_rmssd", "ms"),
    "StepsRecord": ("steps", "count"),
    "ExerciseSessionRecord": ("exercise_minutes", "min"),
    "SleepSessionRecord": ("sleep_duration", "h"),
    "OxygenSaturationRecord": ("oxygen_saturation", "%"),
    "BloodPressureRecord.systolic": ("blood_pressure_systolic", "mmHg"),
    "BloodPressureRecord.diastolic": ("blood_pressure_diastolic", "mmHg"),
    "BodyTemperatureRecord": ("body_temperature", "°C"),
    "BloodGlucoseRecord": ("blood_glucose", "mg/dL"),
    "WeightRecord": ("body_mass", "kg"),
}


class AndroidHealthModule(HealthModule):
    module_id = "android_health"
    version = "1.0.0"
    name = "Android Health Connect bridge"
    description = "Receives Health Connect records uploaded by the HEALTH-01 Android app."
    category = "device"
    data_class = DataClass.real
    supported_metrics = sorted({v[0] for v in HC_MAP.values()})

    def default_config(self) -> dict[str, Any]:
        return {"requires_app": "HEALTH-01 Android (Health Connect, API 28+)",
                "permissions": "explicit READ_* permissions per record type"}

    def map_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        rec = dict(raw)
        rt = rec.pop("record_type", None)
        if rt:
            if rt not in HC_MAP:
                raise ModuleError(f"unsupported Health Connect record type {rt}")
            rec["metric"], rec["unit"] = HC_MAP[rt]
        rec.setdefault("source_device", "Health Connect")
        rec.setdefault("quality", "good")
        return rec
