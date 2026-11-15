"""MQTT live simulator — identity for the separate publisher container.

The container (services/mqtt_simulator) publishes simulated cabin readings.
This module does not generate them. The MQTT bridge stores them with
source_module mqtt_sim once the topics are assigned.
"""
from __future__ import annotations

from typing import Any

from app.modules.base import HealthModule
from app.schemas.measurement import DataClass


class MqttSimModule(HealthModule):
    module_id = "mqtt_sim"
    version = "1.0.0"
    name = "MQTT live simulator"
    description = ("Separate container that publishes simulated cabin readings over MQTT. "
                   "Proves sensor → broker → ingest. ALL DATA SIMULATED.")
    category = "simulation"
    data_class = DataClass.simulated
    supported_metrics = ["cabin_temperature", "cabin_humidity", "cabin_co2", "cabin_pressure", "radiation_dose_rate"]
    accepts_ingest = False

    def default_config(self) -> dict[str, Any]:
        return {
            "command": "docker compose --profile mqtt-sim up -d --build mqtt-sim",
            "wire_command": "scripts/mqtt_sim.ps1",
            "broker": "mosquitto:1883",
            "topics": [
                "habitat/module-a/co2",
                "habitat/module-a/climate",
                "habitat/module-a/pressure",
                "habitat/module-a/radiation",
            ],
        }

    def status(self) -> dict[str, Any]:
        try:
            from app.mqtt import bridge
            state = bridge.status()
        except Exception as e:  # noqa: BLE001 - status must not take the modules page down
            return {"state": "degraded", "detail": str(e)[:200]}
        if state.get("connected"):
            return {"state": "running", "detail": f"broker {state.get('host')} · {state.get('messages', 0)} messages seen"}
        error = state.get("error") or ""
        if error and error not in ("disabled", "connecting"):
            return {"state": "degraded", "detail": error[:200]}
        return {"state": "waiting", "detail": "publisher off — run scripts/mqtt_sim.ps1"}
