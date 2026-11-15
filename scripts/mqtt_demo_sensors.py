"""Publish simulated habitat readings from the host (no extra container).

The publisher lives in services/mqtt_simulator/publish.py. Prefer the Docker
module, which uses the same script:

    .\\scripts\\mqtt_sim.ps1

Host-only:

    pip install paho-mqtt
    python scripts/mqtt_demo_sensors.py --host localhost --port 1883
"""
import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parents[1] / "services" / "mqtt_simulator" / "publish.py"), run_name="__main__")
