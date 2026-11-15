"""Publish SIMULATED habitat sensor readings to MQTT.

This is the publisher for the mqtt-sim module. It does not talk to the API.
Mosquitto carries the messages; the API bridge stores them only after the
topics are assigned (scripts/mqtt_sim.sh does that).

Topics (all labelled simulated once assigned):
  habitat/module-a/co2          plain number, ppm       -> cabin_co2 (ppm -> mmHg)
  habitat/module-a/climate      JSON {"t": °C, "rh": %} -> cabin_temperature, cabin_humidity
  habitat/module-a/pressure     plain number, hPa       -> cabin_pressure (hPa -> kPa)
  habitat/module-a/radiation    JSON {"dose": µGy/h}    -> radiation_dose_rate

  docker compose --profile mqtt-sim up -d --build mqtt-sim
  python services/mqtt_simulator/publish.py --host localhost
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import time

import paho.mqtt.client as mqtt


def readings(elapsed_min: float) -> list[tuple[str, str]]:
    co2 = 2600 + 400 * math.sin(elapsed_min / 3) + random.gauss(0, 60)  # ppm, ISS-like ~2000-4000
    climate = {
        "t": round(22.5 + 0.4 * math.sin(elapsed_min / 8) + random.gauss(0, 0.15), 2),
        "rh": round(45 + 3 * math.sin(elapsed_min / 10) + random.gauss(0, 0.8), 1),
    }
    pressure = 1013 + 1.2 * math.sin(elapsed_min / 12) + random.gauss(0, 0.4)
    dose = max(0.0, 15 + 2 * math.sin(elapsed_min / 6) + random.gauss(0, 0.6))
    return [
        ("habitat/module-a/co2", f"{co2:.0f}"),
        ("habitat/module-a/climate", json.dumps(climate)),
        ("habitat/module-a/pressure", f"{pressure:.1f}"),
        ("habitat/module-a/radiation", json.dumps({"dose": round(dose, 2)})),
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description="Publish simulated habitat readings to MQTT")
    ap.add_argument("--host", default=os.environ.get("MQTT_HOST", "localhost"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    ap.add_argument("--every", type=float, default=float(os.environ.get("MQTT_EVERY", "5")))
    args = ap.parse_args()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="health01-mqtt-sim")
    client.reconnect_delay_set(1, 30)
    client.connect(args.host, args.port)
    client.loop_start()
    started = time.time()
    print(f"mqtt-sim publishing simulated habitat data to {args.host}:{args.port} every {args.every}s (Ctrl+C to stop)")
    try:
        while True:
            elapsed_min = (time.time() - started) / 60
            for topic, payload in readings(elapsed_min):
                client.publish(topic, payload, qos=0)
            print(f"published 4 readings ({elapsed_min:.1f} min into run)")
            time.sleep(args.every)
    except KeyboardInterrupt:
        print("stopped")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
