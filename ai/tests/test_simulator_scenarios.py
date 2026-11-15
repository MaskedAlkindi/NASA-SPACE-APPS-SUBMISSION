"""The simulator's scenarios must move the models in the expected direction (synthetic data, real models)."""
from datetime import date, datetime, timezone

import pytest

from ai.core.data import FrameHealthDataView
from ai.registry.registry import MemoryStateStore, ModelRegistry
from ml.datasets.synthetic import DEFAULT_CREW, Episode, SimConfig, generate_daily

UNITS = {"sleep_duration": "h", "sleep_efficiency": "%", "sleep_midpoint": "h", "resting_heart_rate": "bpm", "hrv_sdnn": "ms",
         "steps": "count", "exercise_minutes": "min", "blood_pressure_systolic": "mmHg", "blood_pressure_diastolic": "mmHg",
         "fatigue_score": "score 1-7", "stress_score": "score 1-10", "mood_score": "score 1-5", "workload_tlx": "score 0-100",
         "body_temperature": "°C", "blood_glucose": "mg/dL", "body_mass": "kg", "reaction_time": "ms"}
RANK = {"none": 0, "info": 1, "caution": 2, "warning": 3}
AID = DEFAULT_CREW[0].astronaut_id


def _view(scenario: str | None, days: int = 45, start_day: int = 40, length: int = 4):
    episodes = [Episode(scenario, start_day, length, 1.0, AID)] if scenario else []
    df = generate_daily(DEFAULT_CREW[:1], SimConfig(days=days, seed=11, start=date(2026, 9, 1), episodes=episodes))
    df = df[df["astronaut_id"] == AID]
    last = df["date"].iloc[min(len(df) - 1, start_day + length - 1)]
    df = df[df["date"] <= last]
    cols = ["date"] + [c for c in UNITS if c in df.columns]
    return FrameHealthDataView(AID, df[cols], UNITS, now=datetime.combine(last, datetime.min.time(), tzinfo=timezone.utc))


@pytest.fixture(scope="module")
def reg():
    return ModelRegistry(state=MemoryStateStore())


def _sev(reg, model_id, view):
    a = reg.run(model_id, view)
    assert a.status in ("ok", "insufficient_data", "abstained"), (model_id, a.status, a.explanation)
    return RANK[a.severity], a


@pytest.mark.parametrize("scenario", ["illness_like", "cardio_anomaly"])
def test_heart_scenarios_raise_illness_signal(reg, scenario):
    base, _ = _sev(reg, "illness_rhr", _view(None))
    hit, a = _sev(reg, "illness_rhr", _view(scenario))
    assert hit >= RANK["caution"] and hit > base, a.explanation
    anomaly, _ = _sev(reg, "legacy_anomaly", _view(scenario))
    assert anomaly >= RANK["info"]


def test_sleep_disruption_shows_in_sleep_model(reg):
    base, _ = _sev(reg, "sleep_hrv", _view(None))
    hit, a = _sev(reg, "sleep_hrv", _view("sleep_disruption"))
    assert hit > base, a.explanation


def test_every_model_runs_on_simulated_data(reg):
    view = _view("illness_like")
    for mid in reg.enabled_ids():
        a = reg.run(mid, view)
        assert a.status != "error", (mid, a.explanation)
