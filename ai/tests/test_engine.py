"""AI engine tests: registry, plug-in contract, data validation, preprocessing, alerts, exercise contracts."""
import json
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ai.adapters.alerts import to_event
from ai.adapters.exercise import ExerciseGuidanceV1, ExerciseSessionSummaryV1, export_schemas, recommend
from ai.core.data import FrameHealthDataView, check_inputs
from ai.core.plugin import ModelPlugin
from ai.core.types import Assessment, FeatureSpec, ModelManifest
from ai.preprocessing.daily_features import FEATURES, build
from ai.preprocessing.signals import causal_baseline, cgm_metrics, clean_rr, homa_ir, hrv_time_domain
from ai.registry.registry import MemoryStateStore, ModelRegistry
from ml.datasets.synthetic import DEFAULT_CREW, Episode, SimConfig, generate_daily

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "ai" / "documentation" / "template_model"
UNITS = {"resting_heart_rate": "bpm", "hrv_sdnn": "ms", "sleep_duration": "h", "sleep_midpoint": "h", "sleep_efficiency": "%",
         "steps": "count", "exercise_minutes": "min", "blood_glucose": "mg/dL", "workload_tlx": "score 0-100", "fatigue_score": "score 1-7"}


def view(aid="AST-001", days=40, episodes=None, seed=3, crew=0, units=None, stale_days=0):
    df = generate_daily([DEFAULT_CREW[crew]], SimConfig(days=days, seed=seed, episodes=episodes or []))
    df["date"] = pd.to_datetime(df["date"])
    now = (df["date"].max() + pd.Timedelta(hours=20) + pd.Timedelta(days=stale_days)).tz_localize("UTC").to_pydatetime()
    return FrameHealthDataView(aid, df, units or UNITS, now=now)


@pytest.fixture(scope="module")
def reg():
    return ModelRegistry(state=MemoryStateStore())


# ------------------------------------------------------------------ registry
def test_discovers_all_models_from_manifests(reg):
    assert set(reg.entries) >= {"fatigue_pmdata", "glucose_metabolic", "illness_rhr", "sleep_hrv", "orthostatic",
                                "legacy_anomaly", "legacy_fatigue_sim", "legacy_forecast"}
    assert reg.invalid == {}
    assert "orthostatic" in reg.enabled_ids()                # every model is on by default (it never raises alerts)


def test_core_has_no_hardcoded_model_references():
    for f in (ROOT / "ai" / "core").glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert "illness_rhr" not in text and "fatigue_pmdata" not in text
    text = (ROOT / "ai" / "registry" / "registry.py").read_text(encoding="utf-8")
    assert "illness_rhr" not in text and "fatigue_pmdata" not in text


def test_external_plugin_folder_and_template(tmp_path, monkeypatch):
    shutil.copytree(TEMPLATE, tmp_path / "template_model")
    monkeypatch.setenv("HMT_AI_MODEL_PATHS", str(tmp_path))
    r = ModelRegistry(state=MemoryStateStore())
    assert "my_new_model" in r.entries and not r.settings("my_new_model")["enabled"]
    r.set_enabled("my_new_model", True)
    a = r.run("my_new_model", view())
    assert a.status == "ok" and a.score > 0


def test_invalid_and_duplicate_manifests_are_reported(tmp_path):
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "manifest.json").write_text('{"id": "Bad Id!", "name": "x"}')
    dup = tmp_path / "dup"
    shutil.copytree(TEMPLATE, dup)
    m = json.loads((dup / "manifest.json").read_text())
    m["id"] = "illness_rhr"
    (dup / "manifest.json").write_text(json.dumps(m))
    r = ModelRegistry(state=MemoryStateStore(), search_paths=[ROOT / "ai" / "models", tmp_path])
    assert any("bad" in k for k in r.invalid) and any("duplicate" in v for v in r.invalid.values())
    assert "illness_rhr" in r.entries                     # original kept


def test_enable_disable_and_threshold_state(reg):
    reg.set_enabled("sleep_hrv", False)
    assert reg.run("sleep_hrv", view()).status == "disabled"
    reg.set_enabled("sleep_hrv", True)
    assert reg.settings("illness_rhr")["thresholds"]["caution_z"] == 3.0


def test_broken_plugin_does_not_crash(tmp_path):
    d = tmp_path / "broken"
    shutil.copytree(TEMPLATE, d)
    m = json.loads((d / "manifest.json").read_text())
    m.update(id="broken", entrypoint="does_not_exist.module:Nope", enabled_by_default=True)
    (d / "manifest.json").write_text(json.dumps(m))
    r = ModelRegistry(state=MemoryStateStore(), search_paths=[tmp_path])
    a = r.run("broken", view())
    assert a.status == "error" and "could not be loaded" in a.explanation


def test_timeout_and_exception_are_isolated(reg):
    class Slow(ModelPlugin):
        def _predict(self, v, q):
            time.sleep(2)
    class Boom(ModelPlugin):
        def _predict(self, v, q):
            raise ValueError("boom")
    base = reg.entries["sleep_hrv"].manifest.model_dump()
    for cls, mid in ((Slow, "slow_test"), (Boom, "boom_test")):
        man = ModelManifest(**{**base, "id": mid, "execution": {**base["execution"], "timeout_s": 0.3}})
        reg.entries[mid] = type(reg.entries["sleep_hrv"])(man, reg.entries["sleep_hrv"].folder)
        reg.entries[mid].plugin = cls(man, reg.entries["sleep_hrv"].folder)
    assert "timed out" in reg.run("slow_test", view()).explanation
    assert reg.run("boom_test", view()).status == "error"
    for mid in ("slow_test", "boom_test"):
        del reg.entries[mid]


# ------------------------------------------------------------------ data validation
def test_input_check_missing_stale_and_units():
    specs = [FeatureSpec(metric="resting_heart_rate", unit="bpm"), FeatureSpec(metric="blood_glucose", unit="mg/dL")]
    q = check_inputs(view(), specs, now=view().last_seen("resting_heart_rate") + timedelta(hours=1))
    assert q["ok"]
    q = check_inputs(view(units={**UNITS, "blood_glucose": "mmol/L"}), specs)
    assert not q["ok"] and q["unit_mismatch"][0]["found"] == "mmol/L"
    v = view(stale_days=5)
    assert not check_inputs(v, specs, now=v._now)["ok"]
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=10), "resting_heart_rate": 60.0})
    assert "blood_glucose" in check_inputs(FrameHealthDataView("A", df, UNITS), specs)["missing"]


def test_models_return_insufficient_data_instead_of_guessing(reg):
    df = pd.DataFrame({"date": pd.date_range(end=pd.Timestamp.utcnow().normalize().tz_localize(None), periods=5),
                       "resting_heart_rate": [60, 61, 59, 60, 62.0], "sleep_duration": 7.0, "blood_glucose": 90.0})
    v = FrameHealthDataView("A", df, UNITS)
    for mid in ("illness_rhr", "fatigue_pmdata", "sleep_hrv"):
        assert reg.run(mid, v).status == "insufficient_data"


# ------------------------------------------------------------------ predictions
def test_every_enabled_model_returns_valid_assessment(reg):
    v = view(episodes=[Episode("illness_like", 37, 3, 1.3, "AST-001")])
    for a in reg.run_all(v):
        assert isinstance(a, Assessment) and a.astronaut_id == "AST-001"
        assert a.status in ("ok", "insufficient_data"), (a.model_id, a.explanation)
        assert a.evidence_level in ("earth_research", "simulation", "rule_based")
        json.dumps(a.model_dump(mode="json"))                # serialisable for the API


def test_illness_model_flags_injected_episode_and_not_nominal(reg):
    sick = reg.run("illness_rhr", view(episodes=[Episode("illness_like", 37, 3, 1.3, "AST-001")]))
    calm = reg.run("illness_rhr", view(seed=11))
    assert sick.severity == "caution" and sick.score >= 3
    assert calm.severity in ("none", "info")
    assert "sensitivity" in sick.calibration                 # real-data evaluation quoted


def test_fatigue_model_never_exceeds_info(reg):
    a = reg.run("fatigue_pmdata", view(episodes=[Episode("fatigue_buildup", 30, 10, 1.5, "AST-001")]))
    assert a.status == "ok" and a.severity in ("none", "info") and 0 <= a.score <= 1


def test_glucose_homa_ir_only_with_real_insulin(reg):
    v = view()
    a = reg.run("glucose_metabolic", v)
    assert a.status == "ok" and "homa_ir" not in a.outputs
    df = v._daily.copy()
    df["fasting_insulin"] = np.nan
    df.loc[df.index[-1], "fasting_insulin"] = 12.0
    v2 = FrameHealthDataView("AST-001", df, {**UNITS, "fasting_insulin": "µIU/mL"}, now=v._now)
    a2 = reg.run("glucose_metabolic", v2)
    expected = round(df["blood_glucose"].iloc[-1] * 12.0 / 405, 2)
    assert a2.outputs["homa_ir"] == expected


# ------------------------------------------------------------------ preprocessing
def test_hrv_time_domain_known_values():
    rr = np.array([0.8, 0.85, 0.8, 0.85] * 10)
    h = hrv_time_domain(rr)
    assert h["rmssd_ms"] == pytest.approx(50.0) and h["mean_hr_bpm"] == pytest.approx(60 / 0.825, rel=1e-3)
    assert h["pnn50_pct"] == 0.0
    assert len(clean_rr(np.array([0.8, 0.81, 3.0, 0.1, 1.5, 0.82]))) == 3     # out of range + 85% jump removed


def test_baseline_has_no_lookahead():
    s = pd.Series([60.0] * 30 + [90.0])
    b = causal_baseline(s, window=28, gap=1, min_periods=7)
    assert b["base_median"].iloc[-1] == 60.0 and b["z"].iloc[-1] > 3
    s2 = s.copy()
    s2.iloc[-1] = 200.0
    assert causal_baseline(s2)["base_median"].iloc[-2] == b["base_median"].iloc[-2]   # future value has no effect


def test_homa_and_cgm_metrics():
    assert homa_ir(90, 10) == pytest.approx(2.22)
    assert homa_ir(90, None) is None and homa_ir(5, 10) is None            # mmol/L passed by mistake is rejected
    m = cgm_metrics(pd.Series([100.0] * 50 + [200.0] * 50))
    assert m["tir_70_180_pct"] == 50.0 and m["tar_180_pct"] == 50.0


def test_daily_features_missing_columns():
    df = pd.DataFrame({"date": pd.date_range("2026-01-01", periods=20), "resting_heart_rate": 60.0})
    f = build(df)
    assert list(f.columns) == ["date"] + FEATURES and f["sleep_h"].isna().all()


# ------------------------------------------------------------------ alerts
def test_alert_events_and_dedupe(reg):
    v = view(episodes=[Episode("illness_like", 37, 3, 1.3, "AST-001")])
    a = reg.run("illness_rhr", v)
    e1 = to_event(a, reg.entries["illness_rhr"].manifest)
    e2 = to_event(a, reg.entries["illness_rhr"].manifest)
    assert e1["kind"] == "concern" and e1["not_a_diagnosis"] and e1["dedupe_key"] == e2["dedupe_key"]
    assert e1["evidence_level"] == "earth_research" and e1["contributing"][0]["metric"] == "resting_heart_rate"
    f = reg.run("fatigue_pmdata", v)
    if f.severity == "info":
        assert to_event(f, reg.entries["fatigue_pmdata"].manifest)["kind"] == "insight"
    none = a.model_copy(update={"severity": "none"})
    assert to_event(none, reg.entries["illness_rhr"].manifest) is None


# ------------------------------------------------------------------ isolation
def test_views_are_per_astronaut(reg):
    a = reg.run("illness_rhr", view(aid="AST-001", crew=0))
    b = reg.run("illness_rhr", view(aid="AST-004", crew=3))
    assert a.astronaut_id == "AST-001" and b.astronaut_id == "AST-004"
    assert a.outputs["baseline_rhr"] != b.outputs["baseline_rhr"]


# ------------------------------------------------------------------ exercise contracts
def test_exercise_contracts_and_conservative_guidance(reg):
    s = ExerciseSessionSummaryV1(session_id="s1", astronaut_id="AST-001", started_at=datetime.now(timezone.utc),
                                 duration_min=45, intensity_rpe=6, completed=True)
    with pytest.raises(Exception):
        ExerciseSessionSummaryV1(session_id="s2", astronaut_id="AST-001", started_at=datetime.now(timezone.utc), intensity_rpe=14)
    g = recommend("AST-001", [], [], [s.model_dump()])
    assert g.readiness == "insufficient_data" and g.adherence_14d["pct"] == 100
    sick = reg.run_all(view(episodes=[Episode("illness_like", 37, 3, 1.3, "AST-001")]))
    g2 = recommend("AST-001", sick, [{"severity": "warning", "category": "vitals", "title": "High body temperature"}], [])
    assert g2.readiness == "rest_and_recheck" and g2.not_medical_advice
    ExerciseGuidanceV1.model_validate(g2.model_dump())


def test_contract_schemas_exported():
    paths = export_schemas()
    names = {p.name for p in paths}
    assert {"exercise_session_summary.v1.json", "exercise_guidance.v1.json", "ai_assessment.v1.json"} <= names
    assert json.loads((ROOT / "contracts" / "exercise_guidance.v1.json").read_text())["title"] == "ExerciseGuidanceV1"
