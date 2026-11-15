import time

from app.assistant import service as assistant_service


def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["database"] and all(body["models"].values()) and body["assistant_mode"] == "offline"


def test_public_session_opens_the_demo(client):
    r = client.post("/api/v1/auth/public")
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "mission_control"
    assert client.get("/api/v1/astronauts", headers={"Authorization": f"Bearer {body['access_token']}"}).status_code == 200


def test_auth_required_and_bad_login(client):
    assert client.get("/api/v1/astronauts").status_code == 401
    assert client.post("/api/v1/auth/login", json={"username": "hajid", "passcode": "nope"}).status_code == 401
    assert client.get("/api/v1/astronauts", headers={"Authorization": "Bearer forged.token"}).status_code == 401


def test_crew_list_and_scoping(client, mc, orion):
    all_ids = [a["id"] for a in client.get("/api/v1/astronauts", headers=mc).json()["astronauts"]]
    assert all_ids == ["AST-001", "AST-002", "AST-003", "AST-004", "AST-005", "AST-900"]
    mine = [a["id"] for a in client.get("/api/v1/astronauts", headers=orion).json()["astronauts"]]
    assert mine == ["AST-001"]
    # astronaut cannot read or write another astronaut's data
    assert client.get("/api/v1/astronauts/AST-002/measurements", headers=orion).status_code == 404
    assert client.get("/api/v1/astronauts/AST-002/predictions", headers=orion).status_code == 404
    r = client.post("/api/v1/measurements", headers=orion, json={"measurements": [
        {"astronaut_id": "AST-002", "metric": "heart_rate", "value": 70, "unit": "bpm", "timestamp": "2026-11-01T00:00:00Z"}]})
    assert r.json()["accepted"] == 0 and r.json()["rejected"] == 1
    assert client.post("/api/v1/simulation/start", headers=orion, json={}).status_code == 403


def test_measurements_and_daily(client, mc):
    r = client.get("/api/v1/astronauts/AST-001/measurements?metric=heart_rate&days=3", headers=mc).json()
    assert r["items"] and all(i["metric"] == "heart_rate" and i["data_class"] == "simulated" for i in r["items"])
    d = client.get("/api/v1/astronauts/AST-001/measurements?resolution=daily&days=30", headers=mc).json()
    assert len(d["items"]) >= 28 and "sleep_duration" in d["metrics"]


def test_upload_via_apple_module_is_idempotent(client, orion):
    rec = {"hk_type": "HKQuantityTypeIdentifierStepCount", "value": 4000, "timestamp": "2026-11-13T22:00:00Z",
           "external_id": "steps-2026-11-13", "source_device": "Apple Watch"}
    r1 = client.post("/api/v1/measurements", headers=orion, json={"module": "apple_health", "measurements": [rec]}).json()
    r2 = client.post("/api/v1/measurements", headers=orion,
                     json={"module": "apple_health", "measurements": [{**rec, "value": 5200}]}).json()
    assert r1["accepted"] == 1 and r2["updated"] == 1 and r2["accepted"] == 0
    mods = {m["id"]: m for m in client.get("/api/v1/modules", headers=orion).json()["modules"]}
    assert mods["apple_health"]["status"]["state"] == "connected"


def test_predictions_and_alert_evidence(client, mc):
    p = client.get("/api/v1/astronauts/AST-004/predictions", headers=mc).json()
    assert p["anomaly"]["latest"]["status"] == "scored"
    assert p["anomaly"]["latest"]["is_anomaly"] is True   # seeded cardio anomaly on the last days
    assert p["fatigue"]["status"] == "estimated" and p["forecasts"]["series"]
    alerts = client.get("/api/v1/astronauts/AST-004/alerts", headers=mc).json()["alerts"]
    assert alerts and all(a["evidence"] for a in alerts)
    assert any(a["category"] in ("anomaly", "cardiovascular") for a in alerts)


def test_mission_overview(client, mc):
    m = client.get("/api/v1/mission", headers=mc).json()
    assert m["crew_count"] == 6 and m["mission_day"] >= 30 and m["data_class"] == "simulated"


def test_assistant_offline_fallback(client, mc):
    r = client.post("/api/v1/assistant/chat", headers=mc,
                    json={"astronaut_id": "AST-004", "message": "Why is my heart rate unusual?"}).json()
    assert r["mode"] == "offline" and "no LLM provider available" in r["fallback_reason"]
    assert "What was measured" in r["answer"] and "not a medical device" in r["answer"]
    r2 = client.post("/api/v1/assistant/chat", headers=mc,
                     json={"astronaut_id": "AST-001", "message": "I have chest pain, how am I doing?"}).json()
    assert "flight surgeon" in r2["answer"].lower()


def test_assistant_openai_path_with_mock(client, mc, monkeypatch):
    captured = {}

    def fake_call(provider, model, messages):
        captured["messages"] = messages
        assert provider == "openai"
        return "Your resting heart rate is 999 bpm.", {"prompt_tokens": 100, "completion_tokens": 20}

    monkeypatch.setattr(assistant_service._settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(assistant_service, "_call_llm", fake_call)
    r = client.post("/api/v1/assistant/chat", headers=mc,
                    json={"astronaut_id": "AST-004", "message": "How am I doing today?",
                          "history": [{"role": "user", "content": f"q{i}"} for i in range(15)]}).json()
    assert r["mode"] == "openai" and "999" in r["grounding_flags"]
    msgs = captured["messages"]
    assert msgs[0]["role"] == "system" and len(msgs) <= 2 + assistant_service._settings.assistant_history_limit
    assert "Osama" not in msgs[-1]["content"] and "Haitham" not in msgs[-1]["content"]  # no real names sent


def test_assistant_chat_job_finishes(client, mc):
    started = client.post("/api/v1/assistant/chat/jobs", headers=mc,
                          json={"astronaut_id": "AST-004", "message": "Why is my heart rate unusual?"})
    assert started.status_code == 200
    job_id = started.json()["id"]
    body = {"status": "pending"}
    deadline = time.time() + 20
    while time.time() < deadline:
        body = client.get(f"/api/v1/assistant/chat/jobs/{job_id}", headers=mc).json()
        if body["status"] != "pending":
            break
        time.sleep(0.1)
    assert body["status"] == "done" and body["mode"] == "offline" and "What was measured" in body["answer"]
    assert client.get("/api/v1/assistant/chat/jobs/missing", headers=mc).status_code == 404


def test_assistant_job_keeps_running_after_the_request_returns(client, mc, monkeypatch):
    import threading

    from app.assistant import jobs as chat_jobs

    release = threading.Event()

    def slow(db, username, astronaut_id, message, history, provider, model):
        release.wait(3)
        return {"answer": "still here", "mode": "offline", "provider": "offline", "model": None,
                "fallback_reason": None, "usage": None, "context_summary": {}, "citations": []}

    monkeypatch.setattr(chat_jobs.assistant, "chat", slow)
    try:
        started = client.post("/api/v1/assistant/chat/jobs", headers=mc,
                              json={"astronaut_id": "AST-004", "message": "How am I doing?"})
        assert started.status_code == 200, started.text
        job_id = started.json()["id"]
        assert client.get(f"/api/v1/assistant/chat/jobs/{job_id}", headers=mc).json()["status"] == "pending"
        release.set()
        body = {"status": "pending"}
        for _ in range(40):
            body = client.get(f"/api/v1/assistant/chat/jobs/{job_id}", headers=mc).json()
            if body["status"] != "pending":
                break
            time.sleep(0.05)
        assert body["status"] == "done" and body["answer"] == "still here"
    finally:
        release.set()


def test_research_endpoints(client, mc):
    from app.api.routes_more import run_nasa_import
    res = run_nasa_import()
    assert res["observations"] > 100
    ds = client.get("/api/v1/research/datasets", headers=mc).json()["datasets"]
    assert any(d["accession"] == "OSD-575" and d["status"] == "downloaded" for d in ds)
    f = client.get("/api/v1/research/findings", headers=mc).json()["findings"]
    assert any(x["evidence_type"] == "computed_from_dataset" for x in f)
    assert any(x["evidence_type"] == "nasa_hrp_risk_page" for x in f)       # official challenge resources
    assert any(x["evidence_type"] == "nasa_report_fact" and x["stats"]["page"] for x in f)
    assert not any(x["evidence_type"] == "curated_summary" for x in f)         # no unsourced paraphrases
    obs = client.get("/api/v1/research/datasets/OSD-569/observations", headers=mc)
    assert obs.status_code == 200 and "WHITE BLOOD CELL COUNT" in obs.json()["analytes"]
    assert all(i["subject_id"] in {"C001", "C002", "C003", "C004"} for i in obs.json()["items"])
    s = client.get("/api/v1/research/search?q=sleep fatigue", headers=mc).json()
    assert s["passages"] and s["passages"][0]["topic"] == "sleep"


def test_simulation_runs_and_streams(client, mc):
    before = client.get("/api/v1/astronauts/AST-001/measurements?metric=heart_rate&days=1", headers=mc).json()["items"][-1]
    r = client.post("/api/v1/simulation/start", headers=mc,
                    json={"scenario": "co2_scrubber_fault", "days": 2, "tick_seconds": 0.05})
    assert r.status_code == 200 and r.json()["running"]
    for _ in range(100):
        st = client.get("/api/v1/simulation/status", headers=mc).json()
        if st.get("ticks", 0) >= 30:
            break
        time.sleep(0.1)
    client.post("/api/v1/simulation/stop", headers=mc)
    assert st["ticks"] >= 30
    after = client.get("/api/v1/astronauts/AST-001/measurements?metric=heart_rate&days=1", headers=mc).json()["items"][-1]
    assert after["timestamp"] > before["timestamp"]
    env = client.get("/api/v1/environment?hours=12", headers=mc).json()
    assert env["series"] and env["summary"]["status"] == "ok"


def test_real_device_user_has_no_simulated_data(client):
    r = client.post("/api/v1/auth/login", json={"username": "pilot", "passcode": "test-pass"})
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    assert r.json()["user"]["astronaut_id"] == "AST-900"
    s = client.get("/api/v1/astronauts/AST-900/summary", headers=h).json()
    assert s["days_of_data"] == 0
    p = client.get("/api/v1/astronauts/AST-900/predictions", headers=h).json()
    assert p["anomaly"]["status"] == "no_data"   # no fabricated predictions without data
    up = client.post("/api/v1/measurements", headers=h, json={"module": "android_health", "measurements": [
        {"record_type": "HeartRateVariabilityRmssdRecord", "value": 48, "timestamp": "2026-11-13T07:00:00Z", "external_id": "x1"},
        {"metric": "fatigue_score", "value": 3, "unit": "score 1-7", "timestamp": "2026-11-13T07:00:00Z"}]}).json()
    assert up["accepted"] == 1 and up["rejected"] == 1   # android module does not accept questionnaire metrics
    d = client.get("/api/v1/astronauts/AST-900/measurements", headers=h).json()["items"]
    assert d[0]["data_class"] == "real" and d[0]["metric"] == "hrv_rmssd"


def test_ollama_provider_selection_and_settings(client, mc, orion, monkeypatch):
    from app.assistant import providers
    monkeypatch.setattr(providers.OllamaProvider, "_list", lambda self: (["qwen2.5:7b"], "1 chat model(s)"))
    calls = []

    def fake_call(provider, model, messages):
        calls.append((provider, model))
        return "Your resting heart rate is above your usual range.", {"prompt_tokens": 50, "completion_tokens": 10}

    monkeypatch.setattr(assistant_service, "_call_llm", fake_call)
    st = client.get("/api/v1/assistant/status", headers=mc).json()
    ollama = next(p for p in st["providers"] if p["id"] == "ollama")
    assert ollama["available"] and ollama["models"] == ["qwen2.5:7b"]
    assert st["active"]["provider"] == "ollama"          # auto: no OpenAI key -> local model
    # per-request choice
    r = client.post("/api/v1/assistant/chat", headers=mc, json={"astronaut_id": "AST-004", "message": "How am I doing?",
                                                                "provider": "ollama", "model": "qwen2.5:7b"}).json()
    assert r["mode"] == "ollama" and r["model"] == "qwen2.5:7b" and calls[-1] == ("ollama", "qwen2.5:7b")
    # invalid model / provider rejected
    bad = client.post("/api/v1/assistant/chat", headers=mc, json={"astronaut_id": "AST-004", "message": "hi",
                                                                  "provider": "ollama", "model": "nope:1b"})
    assert bad.status_code == 422
    assert client.post("/api/v1/assistant/chat", headers=mc, json={"astronaut_id": "AST-004", "message": "hi",
                                                                   "provider": "openai"}).status_code == 422
    # astronauts cannot change the shared default; mission control can
    assert client.put("/api/v1/assistant/settings", headers=orion, json={"provider": "offline"}).status_code == 403
    st2 = client.put("/api/v1/assistant/settings", headers=mc, json={"provider": "offline"}).json()
    assert st2["active"]["provider"] == "offline"
    r2 = client.post("/api/v1/assistant/chat", headers=orion, json={"message": "How am I doing?"}).json()
    assert r2["mode"] == "offline" and r2["fallback_reason"] == "offline explainer selected"
    client.put("/api/v1/assistant/settings", headers=mc, json={"provider": "auto"})


def test_ollama_failure_falls_back(client, mc, monkeypatch):
    from app.assistant import providers
    monkeypatch.setattr(providers.OllamaProvider, "_list", lambda self: (["qwen2.5:7b"], "ok"))

    def boom(provider, model, messages):
        raise providers.ProviderError("timeout")

    monkeypatch.setattr(assistant_service, "_call_llm", boom)
    r = client.post("/api/v1/assistant/chat", headers=mc, json={"astronaut_id": "AST-001", "message": "sleep?",
                                                                "provider": "ollama"}).json()
    assert r["mode"] == "offline" and "ollama request failed" in r["fallback_reason"]
