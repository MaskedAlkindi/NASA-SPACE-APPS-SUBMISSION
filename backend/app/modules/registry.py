"""Module registry: loads each module in isolation so one failure never breaks the app."""
from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT, get_settings
from app.modules.base import HealthModule

log = logging.getLogger("hmt.modules")

MODULE_SPECS = [
    ("apple_health", "app.modules.apple_health.module", "AppleHealthModule"),
    ("android_health", "app.modules.android_health.module", "AndroidHealthModule"),
    ("environment", "app.modules.environment.module", "EnvironmentModule"),
    ("questionnaires", "app.modules.questionnaires.module", "QuestionnaireModule"),
    ("simulation", "app.modules.simulation.module", "SimulationModule"),
    ("mqtt_sim", "app.modules.mqtt_sim.module", "MqttSimModule"),
    ("nasa_osdr", "app.modules.nasa_osdr.module", "NasaOSDRModule"),
    ("nasa_hrp", "app.modules.nasa_hrp.module", "NasaHRPModule"),
    ("exercise", "app.modules.exercise.module", "ExerciseModule"),
    ("nutrition", "app.modules.nutrition.module", "NutritionModule"),
]


class Registry:
    def __init__(self):
        self.modules: dict[str, HealthModule] = {}
        self.failed: dict[str, str] = {}
        disabled = {m.strip() for m in os.getenv("HMT_DISABLED_MODULES", "").split(",") if m.strip()}
        for mid, path, cls in MODULE_SPECS:
            if mid in disabled:
                self.failed[mid] = "disabled by configuration"
                continue
            try:
                klass = getattr(importlib.import_module(path), cls)
                if mid == "nasa_osdr":
                    from app.modules.nasa_osdr.client import OSDRClient
                    s = get_settings()
                    client = OSDRClient(s.nasa_osdr_base, s.nasa_cache_dir, Path(REPO_ROOT) / "data" / "nasa_snapshot",
                                        s.nasa_timeout_s, s.nasa_online)
                    self.modules[mid] = klass(client=client)
                else:
                    self.modules[mid] = klass()
            except Exception as e:  # isolate faulty modules
                log.exception("module %s failed to load", mid)
                self.failed[mid] = f"load error: {e}"

    def get(self, mid: str) -> HealthModule | None:
        return self.modules.get(mid)

    def describe_all(self, ingest_stats: dict[str, dict] | None = None) -> list[dict[str, Any]]:
        out = []
        ingest_stats = ingest_stats or {}
        for mid, _, _ in MODULE_SPECS:
            if mid in self.modules:
                m = self.modules[mid]
                try:
                    st = m.status()
                except Exception as e:
                    st = {"state": "degraded", "detail": f"status error: {e}"}
                d = m.describe()
                stats = ingest_stats.get(mid, {})
                if m.category == "device" and st.get("state") == "available":
                    st = {"state": "connected" if stats.get("count") else "waiting",
                          "detail": "receiving data" if stats.get("count") else "no device data uploaded yet"}
                d.update(status=st, ingest=stats)
                out.append(d)
            else:
                out.append({"id": mid, "status": {"state": "unavailable", "detail": self.failed.get(mid, "")}})
        return out


_registry: Registry | None = None


def get_registry() -> Registry:
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry
