"""Psychological wellbeing check-ins and cognitive testing.

Instruments (scored here, server-side, so every client scores identically):
  samn_perelli  - 7-point fatigue checklist (1 fully alert ... 7 completely exhausted)
  mood          - 1-5 single-item mood rating
  stress        - 1-10 perceived stress rating
  nasa_tlx      - Raw NASA Task Load Index: mean of 6 subscales (0-100)
  reaction_time - PVT-style test: list of trial reaction times (ms); false starts (<100 ms)
                  and lapses (>=500 ms) are counted, mean of valid trials stored
"""
from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Any

from app.modules.base import HealthModule, ModuleError
from app.schemas.measurement import DataClass

INSTRUMENTS = {
    "samn_perelli": {"metric": "fatigue_score", "unit": "score 1-7", "label": "Fatigue check-in (Samn-Perelli)",
                     "options": {1: "Fully alert, wide awake", 2: "Very lively, responsive", 3: "Okay, somewhat fresh",
                                 4: "A little tired, less than fresh", 5: "Moderately tired, let down",
                                 6: "Extremely tired, very difficult to concentrate",
                                 7: "Completely exhausted, unable to function effectively"}},
    "mood": {"metric": "mood_score", "unit": "score 1-5", "label": "Mood", "min": 1, "max": 5},
    "stress": {"metric": "stress_score", "unit": "score 1-10", "label": "Perceived stress", "min": 1, "max": 10},
    "nasa_tlx": {"metric": "workload_tlx", "unit": "score 0-100", "label": "Workload (Raw NASA-TLX)",
                 "subscales": ["mental", "physical", "temporal", "performance", "effort", "frustration"]},
    "reaction_time": {"metric": "reaction_time", "unit": "ms", "label": "Reaction-time test (PVT-style)"},
}


def score(instrument: str, answers: Any) -> tuple[float, dict]:
    if instrument not in INSTRUMENTS:
        raise ModuleError(f"unknown instrument {instrument}")
    spec = INSTRUMENTS[instrument]
    if instrument == "samn_perelli":
        v = int(answers)
        if v not in spec["options"]:
            raise ModuleError("samn_perelli answer must be 1-7")
        return float(v), {"label": spec["options"][v]}
    if instrument in ("mood", "stress"):
        v = float(answers)
        if not spec["min"] <= v <= spec["max"]:
            raise ModuleError(f"{instrument} must be {spec['min']}-{spec['max']}")
        return v, {}
    if instrument == "nasa_tlx":
        if not isinstance(answers, dict) or set(answers) != set(spec["subscales"]):
            raise ModuleError(f"nasa_tlx needs subscales {spec['subscales']}")
        vals = [float(answers[k]) for k in spec["subscales"]]
        if any(not 0 <= v <= 100 for v in vals):
            raise ModuleError("nasa_tlx subscales must be 0-100")
        return round(mean(vals), 1), {"subscales": answers, "method": "raw TLX (unweighted)"}
    # reaction_time
    trials = [float(t) for t in answers]
    if len(trials) < 3:
        raise ModuleError("reaction_time needs at least 3 trials")
    valid = [t for t in trials if t >= 100]
    if not valid:
        raise ModuleError("no valid trials")
    return round(mean(valid), 0), {"trials": len(trials), "false_starts": len(trials) - len(valid),
                                   "lapses_500ms": sum(t >= 500 for t in valid)}


class QuestionnaireModule(HealthModule):
    module_id = "questionnaires"
    version = "1.0.0"
    name = "Wellbeing check-ins & cognitive test"
    description = "Fatigue, mood, stress, NASA-TLX workload and PVT-style reaction-time testing."
    category = "questionnaire"
    data_class = DataClass.real
    supported_metrics = [v["metric"] for v in INSTRUMENTS.values()]

    def default_config(self) -> dict[str, Any]:
        return {"instruments": {k: v["label"] for k, v in INSTRUMENTS.items()}}

    def map_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        rec = dict(raw)
        instrument = rec.pop("instrument", None)
        if instrument:
            value, extra = score(instrument, rec.pop("answers"))
            spec = INSTRUMENTS[instrument]
            rec.update(metric=spec["metric"], unit=spec["unit"], value=value,
                       value_json={"instrument": instrument, **extra})
            rec.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        rec.setdefault("source_device", "self-report")
        rec.setdefault("quality", "good")
        return rec
