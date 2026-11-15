"""Official challenge resources: snapshot integrity, indicator coverage, risk view, vitals rules."""
import pandas as pd

from app.intelligence import alerts as alert_engine
from app.modules.apple_health.module import AppleHealthModule
from app.modules.nasa_hrp.evidence import EVIDENCE
from app.modules.nasa_hrp.extract import normalise
from app.modules.nasa_hrp.module import load
from app.modules.nasa_hrp.sources import RESOURCES
from ml.datasets.synthetic import DEFAULT_CREW, Episode, SimConfig, generate_daily


def test_snapshot_has_every_resource_and_verified_evidence():
    k = load()
    assert k["available"]
    m = k["manifest"]
    assert [r["url"] for r in m["resources"]] == [r["url"] for r in RESOURCES]
    assert all(r["status"] == "downloaded" and len(r["sha256"]) == 64 for r in m["resources"])
    assert m["datasets"] == [] and "no downloadable datasets" in m["datasets_note"]
    assert len(k["hazards"]) == 5 and len(k["risks"]) == 17
    assert len(k["evidence"]) == len(EVIDENCE)          # builder drops anything it could not verify
    for e in k["evidence"]:
        assert e["quote"] and e["source_url"].startswith("https://")
        if e["source"].endswith(".pdf"):
            assert isinstance(e["page"], int) and e["page"] >= 1
    # NASA prevention guidance comes from the pages themselves
    cardio = next(r for r in k["risks"] if r["slug"] == "risk-of-cardiovascular-adaptations")
    assert "exercise" in cardio["what_can_be_done"].lower()


def test_hazard_page_quote_matches_bundled_text():
    k = load()
    page = k["pages"]["hazard-gravity-fields"]
    text = normalise(" ".join(page["sections"].values()))
    assert normalise("1% to 1.5% of mineral density per month") in text


def test_challenge_endpoint_and_indicator_coverage(client, mc):
    ch = client.get("/api/v1/challenge", headers=mc).json()
    assert len(ch["resources"]) == 5 and len(ch["documents"]) == 12
    assert all(x["supported"] for x in ch["indicator_coverage"])
    assert {x["indicator"] for x in ch["indicator_coverage"]} >= {"blood sugar", "body temperature", "mood"}


def test_risk_view_and_scoping(client, mc, orion):
    r = client.get("/api/v1/astronauts/AST-001/risks", headers=mc).json()
    assert r["available"] and len(r["risks"]) == 17 and r["mission_day"] >= 30
    statuses = {x["status"] for x in r["risks"]}
    assert statuses <= {"attention", "watch", "ok", "no_data", "clinical_exam", "not_monitored"}
    sans = next(x for x in r["risks"] if "neuro-ocular" in x["slug"])
    assert sans["status"] == "clinical_exam"
    bone = next(x for x in r["risks"] if "bone" in x["slug"])
    lo, hi = bone["models"]["bone"]["expected_loss_pct"]
    assert 0 < lo < hi and any(e["page"] for e in bone["evidence"])
    assert client.get("/api/v1/astronauts/AST-002/risks", headers=orion).status_code == 404


def test_new_vitals_through_device_module():
    items, errs = AppleHealthModule().ingest([
        {"astronaut_id": "AST-001", "hk_type": "HKQuantityTypeIdentifierBodyTemperature", "value": 37.4, "timestamp": "2026-11-10T07:00:00Z"},
        {"astronaut_id": "AST-001", "hk_type": "HKQuantityTypeIdentifierBloodGlucose", "value": 91, "timestamp": "2026-11-10T07:00:00Z"},
        {"astronaut_id": "AST-001", "hk_type": "HKQuantityTypeIdentifierBodyMass", "value": 70.2, "timestamp": "2026-11-10T07:00:00Z"},
    ])
    assert not errs and [i.metric for i in items] == ["body_temperature", "blood_glucose", "body_mass"]


def _daily(**override):
    df = generate_daily([DEFAULT_CREW[0]], SimConfig(days=30, seed=5, episodes=[Episode("illness_like", 27, 3, 1.3, "AST-001")]))
    df["date"] = pd.to_datetime(df["date"])
    for k, v in override.items():
        df.loc[df.index[-1], k] = v
    return df


def test_temperature_rule_uses_personal_baseline():
    out = alert_engine.evaluate_astronaut(_daily(body_temperature=38.2), "AST-001")
    t = next(a for a in out if a["dedupe_key"].startswith("AST-001:temp_"))
    assert t["severity"] == "caution" and "microgravity" in t["message"]
    assert alert_engine.evaluate_astronaut(_daily(body_temperature=38.9), "AST-001")


def test_glucose_rule_uses_nasa_reference_range(client):
    # the OSDR import (run at startup from the bundled snapshot) provides the reference range
    from app.intelligence.research import lab_reference_range
    assert lab_reference_range("GLUCOSE") == (65.0, 99.0)
    out = alert_engine.evaluate_astronaut(_daily(blood_glucose=104), "AST-001")
    g = next(a for a in out if "glucose" in a["dedupe_key"])
    assert g["severity"] == "info" and "OSD-575" in g["message"]
    assert any(a["severity"] == "warning" for a in alert_engine.evaluate_astronaut(_daily(blood_glucose=48), "AST-001"))
