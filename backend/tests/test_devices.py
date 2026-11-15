import uuid


def test_phone_enrolment_assignment_and_upload(client, mc, orion):
    du = str(uuid.uuid4())
    r = client.post("/api/v1/devices/register", json={"device_uuid": du, "platform": "android", "model": "Pixel 8"})
    assert r.status_code == 200 and r.json()["device"]["status"] == "pending"
    token = r.json()["token"]
    h = {"X-Device-UUID": du, "X-Device-Token": token}

    rec = {"metric": "resting_heart_rate", "value": 61, "unit": "bpm", "timestamp": "2026-11-14T06:00:00Z", "external_id": f"rhr-{du}"}
    assert client.post("/api/v1/devices/upload", headers=h, json={"measurements": [rec]}).status_code == 409   # not assigned yet
    assert client.post("/api/v1/devices/upload", headers={**h, "X-Device-Token": "wrong"}, json={}).status_code == 401

    # astronauts cannot see or assign devices; operators can
    assert client.get("/api/v1/devices", headers=orion).status_code == 403
    listed = client.get("/api/v1/devices", headers=mc).json()["devices"]
    assert any(d["device_uuid"] == du for d in listed)
    a = client.put(f"/api/v1/devices/{du}", headers=mc, json={"astronaut_id": "AST-002", "label": "Vega's phone"}).json()["device"]
    assert a["status"] == "assigned" and a["astronaut_id"] == "AST-002"

    # the phone cannot choose a different astronaut: data goes to the assigned one
    up = client.post("/api/v1/devices/upload", headers=h, json={
        "measurements": [{**rec, "astronaut_id": "AST-001"}],
        "workouts": [{"source": "camera", "started_at": "2026-11-14T07:00:00Z", "ended_at": "2026-11-14T07:10:00Z",
                      "exercises": [{"exercise_id": "squat", "sets": [{"reps": 12}]}], "client_id": "w1"}]}).json()
    assert up["accepted"] + up["updated"] == 1 and up["workouts"] == 1 and up["astronaut_id"] == "AST-002", up
    me = client.get("/api/v1/devices/me", headers=h).json()["device"]
    assert me["uploads"] == 1 and me["callsign"]

    # re-registering an enrolled UUID without its token is refused
    assert client.post("/api/v1/devices/register", json={"device_uuid": du, "platform": "android"}).status_code == 409
    assert client.post(f"/api/v1/devices/{du}/revoke", headers=mc).json()["device"]["status"] == "revoked"
    assert client.post("/api/v1/devices/upload", headers=h, json={}).status_code == 403


def test_server_connections_are_operator_managed(client, mc, orion):
    kinds = {c["id"] for c in client.get("/api/v1/servers/connectors", headers=orion).json()["connectors"]}
    assert {"noaa_swpc", "health01_peer", "ollama", "json_feed"} <= kinds
    body = {"name": "Lab gateway", "kind": "json_feed", "url": "http://127.0.0.1:9/feed", "settings": {"token": "abc"}}
    assert client.post("/api/v1/servers", headers=orion, json=body).status_code == 403
    c = client.post("/api/v1/servers", headers=mc, json=body).json()["connection"]
    assert c["last_status"] == "error" and c["settings"]["token"] == "•••"     # unreachable in tests; secret masked
    assert client.post("/api/v1/servers", headers=mc, json={**body, "kind": "nope"}).status_code == 422
    assert client.delete(f"/api/v1/servers/{c['id']}", headers=mc).json()["deleted"] == c["id"]
