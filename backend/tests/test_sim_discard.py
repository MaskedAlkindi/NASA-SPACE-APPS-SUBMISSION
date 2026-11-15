import time


def test_discard_simulation_restores_real_state(client, mc):
    r = client.post("/api/v1/simulation/start", headers=mc, json={"scenario": "illness_like", "astronaut_id": "AST-003", "days": 2, "tick_seconds": 0.05})
    assert r.status_code == 200
    for _ in range(100):
        st = client.get("/api/v1/simulation/status", headers=mc).json()
        if st.get("ticks", 0) >= 20:
            break
        time.sleep(0.1)
    client.post("/api/v1/simulation/stop", headers=mc)
    st = client.get("/api/v1/simulation/status", headers=mc).json()
    assert st["discardable"] is True and st["server_time"]
    d = client.post("/api/v1/simulation/discard", headers=mc).json()
    assert d["discarded"] and d["measurements"] > 0
    st = client.get("/api/v1/simulation/status", headers=mc).json()
    assert st["discardable"] is False and not st.get("running")
    # no simulated reading is left after the simulation's start
    hr = client.get("/api/v1/astronauts/AST-003/measurements?metric=heart_rate&days=30", headers=mc).json()["items"]
    assert all(i["timestamp"] <= d["time"] for i in hr)
