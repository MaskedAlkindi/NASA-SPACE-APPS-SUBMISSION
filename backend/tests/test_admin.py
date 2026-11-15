def _login(client, u, p):
    return client.post("/api/v1/auth/login", json={"username": u, "passcode": p})


def test_extra_mission_control_passcodes(client, mc, orion):
    assert client.get("/api/v1/admin/passcodes", headers=orion).status_code == 403
    assert _login(client, "mission-control", "guest-pass-1").status_code == 401
    p = client.post("/api/v1/admin/passcodes", headers=mc, json={"label": "Judges", "passcode": "guest-pass-1"}).json()
    assert client.post("/api/v1/admin/passcodes", headers=mc, json={"label": "dup", "passcode": "guest-pass-1"}).status_code == 409
    r = _login(client, "mission-control", "guest-pass-1")
    assert r.status_code == 200 and r.json()["user"]["role"] == "mission_control"
    assert _login(client, "hajid", "guest-pass-1").status_code == 401          # only works for Mission Control
    listed = client.get("/api/v1/admin/passcodes", headers=mc).json()["passcodes"]
    assert any(x["id"] == p["id"] and x["last_used"] for x in listed)
    client.delete(f"/api/v1/admin/passcodes/{p['id']}", headers=mc)
    assert _login(client, "mission-control", "guest-pass-1").status_code == 401


def test_crew_management(client, mc):
    crew = {c["id"]: c for c in client.get("/api/v1/admin/crew", headers=mc).json()["crew"]}
    assert crew["AST-001"]["name"] == "Hajid Alkindi" and crew["AST-001"]["login"] == "hajid"
    assert {c["login"] for c in crew.values()} >= {"hajid", "osama", "hamood", "haitham", "mohmmed"}
    assert crew["AST-005"]["measurements"] > 0
    client.put("/api/v1/admin/crew/AST-003", headers=mc, json={"role": "Payload Specialist"})
    assert client.get("/api/v1/admin/crew", headers=mc).json()["crew"][2]["role"] == "Payload Specialist"
    client.put("/api/v1/admin/crew/AST-003", headers=mc, json={"role": "Mission Specialist"})
