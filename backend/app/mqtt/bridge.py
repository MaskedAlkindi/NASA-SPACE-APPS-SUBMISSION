"""MQTT → HEALTH-01 measurements.

One background client (paho-mqtt). It subscribes to every mapped topic plus the "discover" pattern, remembers the
last payload of each topic it sees (so the UI can offer them for assignment), and turns mapped messages into
normal measurements through the same ingestion path as every other module.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import OrderedDict
from datetime import datetime, timezone

from sqlalchemy import select

from app.database.session import SessionLocal
from app.mqtt.db_models import MqttBroker, MqttMapping

log = logging.getLogger("hmt.mqtt")
_lock = threading.Lock()
_client = None
_state = {"connected": False, "error": "", "host": None, "since": None, "messages": 0}
_seen: "OrderedDict[str, dict]" = OrderedDict()      # topic -> {payload, at, count}
_last_store: dict[int, float] = {}
SEEN_MAX = 200


def topic_matches(pattern: str, topic: str) -> bool:
    p, t = pattern.split("/"), topic.split("/")
    for i, part in enumerate(p):
        if part == "#":
            return True
        if i >= len(t) or (part != "+" and part != t[i]):
            return False
    return len(p) == len(t)


def extract(payload: bytes, json_path: str) -> float:
    text = payload.decode("utf-8", "replace").strip()
    if not json_path:
        try:
            return float(text)
        except ValueError:
            obj = json.loads(text)
            if isinstance(obj, dict) and "value" in obj:
                return float(obj["value"])
            raise ValueError("payload is not a number; set a JSON path")
    obj = json.loads(text)
    for key in json_path.split("."):
        obj = obj[int(key)] if isinstance(obj, list) else obj[key]
    return float(obj)


def handle_message(topic: str, payload: bytes, now: float | None = None) -> int:
    """Store a message if a mapping matches. Returns the number of readings stored (also used by tests)."""
    from app.intelligence.ingest import ingest
    from app.schemas.measurement import NormalizedMeasurement
    from app.schemas.metrics import METRICS
    now = now or time.time()
    with _lock:
        _state["messages"] += 1
        entry = _seen.pop(topic, {"count": 0})
        entry.update(payload=payload[:300].decode("utf-8", "replace"), at=datetime.now(timezone.utc).isoformat(), count=entry["count"] + 1)
        _seen[topic] = entry
        while len(_seen) > SEEN_MAX:
            _seen.popitem(last=False)
    db = SessionLocal()
    stored = 0
    try:
        maps = db.execute(select(MqttMapping).where(MqttMapping.enabled.is_(True))).scalars().all()
        items = []
        for m in maps:
            if not topic_matches(m.topic, topic):
                continue
            try:
                value = extract(payload, m.json_path) * m.scale + m.offset
                m.last_value, m.last_at, m.last_error = round(value, 4), datetime.now(timezone.utc), ""
                if now - _last_store.get(m.id, 0) < m.min_interval_s:
                    continue
                _last_store[m.id] = now
                mdef = METRICS[m.metric]
                items.append(NormalizedMeasurement(
                    astronaut_id=m.astronaut_id if mdef.per_astronaut else None, metric=m.metric, value=value, unit=mdef.unit,
                    timestamp=datetime.now(timezone.utc), source_device=f"mqtt:{topic}"[:120],
                    source_module="mqtt_sim" if m.data_class == "simulated" else "habitat_mqtt",
                    data_class=m.data_class))
            except Exception as e:   # noqa: BLE001 - shown next to the mapping
                m.last_error = f"{type(e).__name__}: {str(e)[:200]}"
        db.commit()
        if items:
            ingest(db, items)
            stored = len(items)
    finally:
        db.close()
    return stored


def seen_topics() -> list[dict]:
    with _lock:
        return [{"topic": t, **v} for t, v in reversed(_seen.items())]


def status() -> dict:
    return dict(_state)


def _topics(db) -> list[str]:
    b = db.get(MqttBroker, 1)
    maps = db.execute(select(MqttMapping.topic).where(MqttMapping.enabled.is_(True))).scalars().all()
    return sorted({*(maps or []), *([b.discover] if b and b.discover else [])})


def resubscribe() -> None:
    if _client is None:
        return
    db = SessionLocal()
    try:
        for t in _topics(db):
            _client.subscribe(t, qos=0)
    finally:
        db.close()


def stop() -> None:
    global _client
    if _client is not None:
        try:
            _client.loop_stop()
            _client.disconnect()
        except Exception:   # noqa: BLE001
            pass
    _client = None
    _state.update(connected=False)


def start() -> dict:
    """(Re)connect with the stored broker settings. Safe to call repeatedly."""
    global _client
    stop()
    db = SessionLocal()
    try:
        b = db.get(MqttBroker, 1)
        if b is None or not b.enabled:
            _state.update(connected=False, error="disabled", host=None)
            return status()
        host, port, user, pw, tls = b.host, b.port, b.username, b.password, b.tls
    finally:
        db.close()
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        _state.update(error="paho-mqtt not installed")
        return status()

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"health01-{int(time.time())}")
    if user:
        c.username_pw_set(user, pw or None)
    if tls:
        c.tls_set()

    def on_connect(client, userdata, flags, reason_code, properties=None):
        ok = not getattr(reason_code, "is_failure", False)
        _state.update(connected=ok, error="" if ok else str(reason_code), since=datetime.now(timezone.utc).isoformat())
        if ok:
            resubscribe()

    def on_disconnect(client, userdata, flags, reason_code, properties=None):
        _state.update(connected=False, error=str(reason_code) if reason_code else "")

    def on_message(client, userdata, msg):
        try:
            handle_message(msg.topic, msg.payload)
        except Exception:   # noqa: BLE001 - one bad message never stops the bridge
            log.exception("mqtt message failed (%s)", msg.topic)

    c.on_connect, c.on_disconnect, c.on_message = on_connect, on_disconnect, on_message
    c.reconnect_delay_set(1, 30)
    _state.update(host=f"{host}:{port}", error="connecting")
    try:
        c.connect_async(host, port, keepalive=30)
        c.loop_start()
        _client = c
    except Exception as e:   # noqa: BLE001
        _state.update(connected=False, error=str(e)[:200])
    return status()
