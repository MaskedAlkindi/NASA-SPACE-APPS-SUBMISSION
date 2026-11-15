"""Install the simulated MQTT topic assignments used by the mqtt-sim publisher.

The publisher (services/mqtt_simulator/publish.py) only writes to the broker.
These mappings are what turn those messages into stored measurements.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mqtt.db_models import MqttBroker, MqttMapping

# Keep in step with the topics in services/mqtt_simulator/publish.py.
SIM_MAPPINGS = [
    {"topic": "habitat/module-a/co2", "metric": "cabin_co2", "json_path": "", "scale": 0.00076, "offset": 0.0,
     "label": "Module A CO₂", "min_interval_s": 5.0},
    {"topic": "habitat/module-a/climate", "metric": "cabin_temperature", "json_path": "t", "scale": 1.0, "offset": 0.0,
     "label": "Module A temperature", "min_interval_s": 5.0},
    {"topic": "habitat/module-a/climate", "metric": "cabin_humidity", "json_path": "rh", "scale": 1.0, "offset": 0.0,
     "label": "Module A humidity", "min_interval_s": 5.0},
    {"topic": "habitat/module-a/pressure", "metric": "cabin_pressure", "json_path": "", "scale": 0.1, "offset": 0.0,
     "label": "Module A pressure", "min_interval_s": 5.0},
    {"topic": "habitat/module-a/radiation", "metric": "radiation_dose_rate", "json_path": "dose", "scale": 1.0, "offset": 0.0,
     "label": "Module A radiation", "min_interval_s": 5.0},
]


def install(db: Session, host: str, port: int) -> list[MqttMapping]:
    """Point the bridge at the broker and upsert the simulated habitat mappings. Idempotent."""
    broker = db.get(MqttBroker, 1)
    if broker is None:
        broker = MqttBroker(id=1)
        db.add(broker)
    broker.host = host.strip()
    broker.port = port
    broker.tls = False
    broker.discover = "habitat/#"
    broker.enabled = True
    broker.updated_at = datetime.now(timezone.utc)

    existing = db.execute(select(MqttMapping)).scalars().all()
    by_key = {(m.topic, m.metric, m.json_path): m for m in existing}
    rows: list[MqttMapping] = []
    for spec in SIM_MAPPINGS:
        row = by_key.get((spec["topic"], spec["metric"], spec["json_path"]))
        if row is None:
            row = MqttMapping(astronaut_id=None, data_class="simulated", enabled=True, **spec)
            db.add(row)
        else:
            for key, value in spec.items():
                setattr(row, key, value)
            row.data_class = "simulated"
            row.enabled = True
        rows.append(row)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows
