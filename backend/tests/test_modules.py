import pytest

from app.modules.android_health.module import AndroidHealthModule
from app.modules.apple_health.module import AppleHealthModule
from app.modules.base import ModuleError
from app.modules.environment.module import EnvironmentModule
from app.modules.questionnaires.module import QuestionnaireModule, score
from app.modules.registry import Registry

TS = "2026-11-10T07:00:00Z"


def test_apple_maps_healthkit_identifiers_and_units():
    m = AppleHealthModule()
    items, errs = m.ingest([
        {"astronaut_id": "AST-001", "hk_type": "HKQuantityTypeIdentifierHeartRate", "value": 61, "timestamp": TS},
        {"astronaut_id": "AST-001", "hk_type": "HKQuantityTypeIdentifierOxygenSaturation", "value": 0.97, "timestamp": TS},
    ])
    assert not errs
    assert items[0].metric == "heart_rate" and items[0].unit == "bpm" and items[0].source_module == "apple_health"
    assert items[1].metric == "oxygen_saturation" and items[1].value == pytest.approx(97)
    assert items[0].data_class.value == "real"


def test_android_keeps_rmssd_separate_from_sdnn():
    m = AndroidHealthModule()
    items, errs = m.ingest([{"astronaut_id": "AST-001", "record_type": "HeartRateVariabilityRmssdRecord",
                             "value": 42, "timestamp": TS}])
    assert not errs and items[0].metric == "hrv_rmssd"


def test_validation_rejects_bad_unit_range_and_unknown_metric():
    m = AppleHealthModule()
    _, errs = m.ingest([
        {"astronaut_id": "AST-001", "metric": "heart_rate", "value": 60, "unit": "Hz", "timestamp": TS},
        {"astronaut_id": "AST-001", "metric": "heart_rate", "value": 900, "unit": "bpm", "timestamp": TS},
        {"astronaut_id": "AST-001", "metric": "cabin_co2", "value": 2, "unit": "mmHg", "timestamp": TS},
        {"metric": "heart_rate", "value": 60, "unit": "bpm", "timestamp": TS},
    ])
    assert len(errs) == 4


def test_environment_is_habitat_wide():
    items, errs = EnvironmentModule().ingest([{"astronaut_id": "AST-001", "metric": "cabin_co2", "value": 2.5,
                                               "unit": "mmHg", "timestamp": TS}])
    assert not errs and items[0].astronaut_id is None


def test_questionnaire_scoring():
    assert score("nasa_tlx", {k: 60 for k in ["mental", "physical", "temporal", "performance", "effort", "frustration"]})[0] == 60
    v, extra = score("reaction_time", [250, 260, 50, 600])
    assert v == pytest.approx(370) and extra["false_starts"] == 1 and extra["lapses_500ms"] == 1
    with pytest.raises(ModuleError):
        score("samn_perelli", 9)
    items, errs = QuestionnaireModule().ingest([{"astronaut_id": "AST-001", "instrument": "samn_perelli", "answers": 5, "timestamp": TS}])
    assert not errs and items[0].metric == "fatigue_score" and items[0].value == 5


def test_registry_isolates_disabled_module(monkeypatch):
    monkeypatch.setenv("HMT_DISABLED_MODULES", "android_health")
    reg = Registry()
    assert reg.get("android_health") is None and reg.get("apple_health") is not None
    desc = {d["id"]: d for d in reg.describe_all()}
    assert desc["android_health"]["status"]["state"] == "unavailable"
    assert reg.get("mqtt_sim") is not None and reg.get("mqtt_sim").accepts_ingest is False
