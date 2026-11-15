import json


def test_mqtt_mapping_extraction_and_ingest(client, mc, orion):
    from app.mqtt import bridge
    assert bridge.topic_matches("habitat/+/co2", "habitat/module-a/co2")
    assert bridge.topic_matches("habitat/#", "habitat/module-a/climate")
    assert not bridge.topic_matches("habitat/+/co2", "habitat/module-a/climate")
    assert bridge.extract(b'{"t": 22.4, "rh": 45}', "t") == 22.4
    assert bridge.extract(b"2600", "") == 2600

    assert client.post("/api/v1/mqtt/mappings", headers=orion, json={"topic": "habitat/+/co2", "metric": "cabin_co2"}).status_code == 403
    assert client.post("/api/v1/mqtt/mappings", headers=mc, json={"topic": "x", "metric": "heart_rate"}).status_code == 422   # needs a person
    m = client.post("/api/v1/mqtt/mappings", headers=mc, json={
        "topic": "habitat/+/co2", "metric": "cabin_co2", "scale": 0.00076, "data_class": "simulated", "min_interval_s": 0}).json()["mapping"]
    p = client.post("/api/v1/mqtt/preview", headers=mc, json={"payload": json.dumps({"t": 71.6}), "json_path": "t",
                                                               "scale": 0.5555556, "offset": -17.7777778}).json()
    assert p["ok"] and abs(p["value"] - 22.0) < 0.01

    assert bridge.handle_message("habitat/module-a/co2", b"3000") == 1          # 3000 ppm -> 2.28 mmHg, stored
    from app.database.models import Measurement
    from app.database.session import SessionLocal
    from sqlalchemy import select
    db = SessionLocal()
    try:
        row = db.execute(select(Measurement).where(Measurement.source_device == "mqtt:habitat/module-a/co2")).scalar_one()
        assert row.source_module == "mqtt_sim" and row.data_class == "simulated"
    finally:
        db.close()
    o = client.get("/api/v1/mqtt", headers=orion).json()
    got = next(x for x in o["mappings"] if x["id"] == m["id"])
    assert abs(got["last_value"] - 2.28) < 0.01 and got["last_error"] == ""
    assert any(s["topic"] == "habitat/module-a/co2" for s in o["seen"])        # shown for assignment
    assert bridge.handle_message("habitat/module-a/unknown", b"1") == 0
    env = client.get("/api/v1/environment?hours=48", headers=mc).json()
    assert any(abs((r.get("cabin_co2") or 0) - 2.28) < 0.01 for r in env["series"])
    assert client.delete(f"/api/v1/mqtt/mappings/{m['id']}", headers=mc).json()["deleted"] == m["id"]


def test_sim_pipeline_assigns_publisher_topics(client, mc, orion):
    from app.mqtt import bridge
    assert client.post("/api/v1/mqtt/sim-pipeline", headers=orion, json={}).status_code == 403
    body = client.post("/api/v1/mqtt/sim-pipeline", headers=mc, json={"host": "mosquitto", "port": 1883})
    assert body.status_code == 200, body.text
    data = body.json()
    assert data["broker"]["enabled"] is True and data["broker"]["host"] == "mosquitto"
    assert len(data["installed"]) == 5
    assert {m["data_class"] for m in data["installed"]} == {"simulated"}
    again = client.post("/api/v1/mqtt/sim-pipeline", headers=mc, json={"host": "mosquitto", "port": 1883}).json()
    assert sorted(m["id"] for m in again["installed"]) == sorted(m["id"] for m in data["installed"])
    try:
        assert bridge.handle_message("habitat/module-a/climate", b'{"t": 22.4, "rh": 46}') == 2
    finally:
        for row in data["installed"]:
            client.delete(f"/api/v1/mqtt/mappings/{row['id']}", headers=mc)
        bridge.stop()
