"""AI engine integration: API, registry state, alerts bridge, isolation, exercise contracts."""
from datetime import datetime, timedelta, timezone


def test_models_listed_with_provenance_and_reports(client, mc):
    r = client.get("/api/v1/ai/models", headers=mc).json()
    ids = {m["id"]: m for m in r["models"]}
    assert {"illness_rhr", "fatigue_pmdata", "glucose_metabolic", "sleep_hrv", "orthostatic", "legacy_anomaly"} <= set(ids)
    assert r["invalid_manifests"] == {}
    ill = ids["illness_rhr"]
    assert ill["evidence_level"] == "earth_research" and ill["validated_on_astronauts"] is False
    assert ill["has_report"] and ill["report"]["held_out_half"]["sensitivity"] is not None
    assert ids["orthostatic"]["enabled"] is True and ids["orthostatic"]["status"] == "research_prototype"


def test_enable_disable_requires_crew_wide(client, mc, orion):
    assert client.put("/api/v1/ai/models/sleep_hrv", headers=orion, json={"enabled": False}).status_code == 403
    r = client.put("/api/v1/ai/models/sleep_hrv", headers=mc, json={"enabled": False}).json()
    assert r["enabled"] is False
    run = client.post("/api/v1/ai/astronauts/AST-001/run?model_id=sleep_hrv", headers=mc).json()
    assert run["assessments"][0]["status"] == "disabled"
    assert client.put("/api/v1/ai/models/sleep_hrv", headers=mc, json={"enabled": True}).json()["enabled"] is True
    assert client.put("/api/v1/ai/models/illness_rhr", headers=mc, json={"thresholds": {"bogus": 1}}).status_code == 422


def test_assessments_and_alert_bridge(client, mc):
    r = client.post("/api/v1/ai/astronauts/AST-004/run", headers=mc).json()      # seeded cardio anomaly on ATLAS
    by = {a["model_id"]: a for a in r["assessments"]}
    assert by["illness_rhr"]["status"] == "ok" and by["illness_rhr"]["severity"] == "caution"
    assert all(a["evidence_level"] in ("earth_research", "simulation", "rule_based") for a in r["assessments"])
    alerts = client.get("/api/v1/astronauts/AST-004/alerts?limit=200", headers=mc).json()["alerts"]
    ai = [a for a in alerts if a["source"].startswith("ai:illness_rhr")]
    assert ai and "not validated on astronauts" in ai[0]["message"].lower()
    again = client.post("/api/v1/ai/astronauts/AST-004/run", headers=mc).json()
    assert not [a for a in again["alerts_created"] if a["source"].startswith("ai:illness_rhr")]   # de-duplicated
    latest = client.get("/api/v1/ai/astronauts/AST-004/assessments", headers=mc).json()["assessments"]
    assert {a["model_id"] for a in latest} >= {"illness_rhr", "fatigue_pmdata"}


def test_imported_model_set_files_an_alert(client, mc, orion):
    sample = client.get("/api/v1/ai/models/sample", headers=mc).json()
    assert sample["id"] == "fatigue_buildup" and sample["metric"] == "fatigue_score" and sample["emit_alerts"] is True
    body = {
        "format": "health01-model-set", "id": "demo_hr_line", "name": "Demo heart-rate line",
        "metric": "resting_heart_rate", "mode": "value", "direction": "above",
        "caution_value": 1, "warning_value": 200, "min_days": 1, "emit_alerts": True, "min_severity": "caution",
    }
    assert client.post("/api/v1/ai/models/import", headers=orion, json=body).status_code == 403
    assert client.post("/api/v1/ai/models/import", headers=mc, json={"id": "illness_rhr", "metric": "resting_heart_rate", "mode": "value", "caution_value": 1}).status_code == 409
    try:
        saved = client.post("/api/v1/ai/models/import", headers=mc, json=body)
        assert saved.status_code == 200, saved.text
        assert saved.json()["imported"] is True and saved.json()["alerting"]["emit_alerts"] is True
        run = client.post("/api/v1/ai/astronauts/AST-004/run?model_id=demo_hr_line", headers=mc).json()
        assert run["assessments"][0]["status"] == "ok"
        assert run["assessments"][0]["severity"] in ("caution", "warning")
        assert any(a["source"].startswith("ai:demo_hr_line") for a in run["alerts_created"])
        listed = {m["id"]: m for m in client.get("/api/v1/ai/models", headers=mc).json()["models"]}
        assert listed["demo_hr_line"]["imported"] is True
    finally:
        client.delete("/api/v1/ai/models/demo_hr_line", headers=mc)


def test_profile_isolation(client, orion):
    assert client.get("/api/v1/ai/astronauts/AST-002/assessments", headers=orion).status_code == 404
    assert client.post("/api/v1/ai/astronauts/AST-002/run", headers=orion).status_code == 404
    assert client.get("/api/v1/ai/astronauts/AST-002/exercise-guidance", headers=orion).status_code == 404
    own = client.get("/api/v1/ai/astronauts/AST-001/assessments", headers=orion).json()
    assert all(a["astronaut_id"] == "AST-001" for a in own["assessments"])


def test_exercise_contracts(client, mc, orion):
    now = datetime.now(timezone.utc)
    s = {"session_id": "cursor-1", "astronaut_id": "AST-001", "started_at": (now - timedelta(days=1)).isoformat(),
         "duration_min": 40, "intensity_rpe": 6, "completed": True, "planned": True}
    r = client.post("/api/v1/ai/exercise/session-summaries", headers=orion, json={"sessions": [s]}).json()
    assert r["accepted"] + r["updated"] == 1
    bad = {**s, "astronaut_id": "AST-002", "session_id": "x"}
    assert client.post("/api/v1/ai/exercise/session-summaries", headers=orion, json={"sessions": [bad]}).status_code == 404
    assert client.post("/api/v1/ai/exercise/session-summaries", headers=orion,
                       json={"sessions": [{**s, "intensity_rpe": 15}]}).status_code == 422
    g = client.get("/api/v1/ai/astronauts/AST-004/exercise-guidance", headers=mc).json()
    assert g["schema_version"] == "exercise_guidance.v1" and g["not_medical_advice"] is True
    assert g["readiness"] in ("reduce_intensity", "rest_and_recheck")              # ATLAS has an active anomaly
    c = client.get("/api/v1/ai/contracts", headers=mc).json()["contracts"]
    assert {"exercise_session_summary.v1", "exercise_guidance.v1", "ai_assessment.v1"} <= set(c)


def test_ingestion_still_works_with_ai_hook(client, orion):
    r = client.post("/api/v1/measurements", headers=orion, json={"measurements": [
        {"metric": "fasting_insulin", "value": 9.5, "unit": "µIU/mL", "timestamp": datetime.now(timezone.utc).isoformat()}]})
    assert r.status_code == 200 and r.json()["accepted"] == 1
