"""Shared, versioned contracts between the AI engine and the exercise module.

The exercise module is developed separately. It talks to the AI engine only through:

  IN  (exercise -> AI):  ExerciseSessionSummaryV1   POST /api/v1/ai/exercise/session-summaries
  OUT (AI -> exercise):  ExerciseGuidanceV1         GET  /api/v1/ai/astronauts/{id}/exercise-guidance

JSON Schemas are exported to contracts/ (see `export_schemas`). Bump the version
suffix for any breaking change; keep old versions until both sides have moved.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ai.core.types import Assessment

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"


class ExerciseSessionSummaryV1(BaseModel):
    """A completed (or planned/missed) exercise session, as reported by the exercise module."""
    schema_version: Literal["exercise_session_summary.v1"] = "exercise_session_summary.v1"
    session_id: str = Field(..., max_length=80)
    astronaut_id: str = Field(..., max_length=32, pattern=r"^[A-Za-z0-9_\-]+$")
    started_at: datetime
    ended_at: datetime | None = None
    activity_type: str = Field("unspecified", max_length=40)      # e.g. aerobic, resistive, treadmill, cycle_ergometer
    planned: bool = True
    completed: bool = True
    duration_min: float | None = Field(None, ge=0, le=600)
    intensity_rpe: float | None = Field(None, ge=0, le=10)         # Borg CR-10 style 0-10
    avg_heart_rate: float | None = Field(None, ge=25, le=230)
    max_heart_rate: float | None = Field(None, ge=25, le=230)
    training_load: float | None = Field(None, ge=0)               # e.g. sRPE = RPE x minutes
    goal_id: str | None = None
    goal_progress_pct: float | None = Field(None, ge=0, le=1000)
    source_module: str = Field("exercise", max_length=40)
    data_class: Literal["real", "simulated"] = "real"


class ExerciseGuidanceV1(BaseModel):
    """What the exercise module may consume from the AI engine."""
    schema_version: Literal["exercise_guidance.v1"] = "exercise_guidance.v1"
    astronaut_id: str
    generated_at: datetime
    readiness: Literal["proceed", "reduce_intensity", "rest_and_recheck", "insufficient_data"]
    recommendation: str
    rationale: list[str]
    fatigue: dict | None = None             # latest fatigue/recovery assessment summary
    sleep: dict | None = None
    anomalies: list[dict] = []              # physiological anomaly assessments at caution or above
    active_alerts: list[dict] = []          # health alerts relevant to exercise (warning/caution)
    adherence_14d: dict | None = None       # computed from exercise sessions / exercise minutes
    source_models: list[str] = []
    limitations: list[str] = []
    not_medical_advice: bool = True


def _summ(a: Assessment) -> dict:
    return {"model_id": a.model_id, "model_version": a.model_version, "status": a.status, "severity": a.severity,
            "score": a.score, "score_label": a.score_label, "scale": a.scale, "explanation": a.explanation,
            "evidence_level": a.evidence_level}


def adherence(sessions: list[dict], daily_exercise_min: list[float] | None = None, target_min: float = 90.0) -> dict | None:
    """Adherence from session summaries if available, else from daily exercise minutes."""
    planned = [s for s in sessions if s.get("planned", True)]
    if planned:
        done = sum(1 for s in planned if s.get("completed"))
        return {"source": "exercise_sessions", "planned": len(planned), "completed": done,
                "pct": round(100 * done / len(planned), 0)}
    if daily_exercise_min:
        vals = [v for v in daily_exercise_min if v == v]
        if vals:
            return {"source": "exercise_minutes", "days": len(vals), "target_min": target_min,
                    "pct": round(100 * sum(v >= target_min for v in vals) / len(vals), 0)}
    return None


def recommend(astronaut_id: str, assessments: list[Assessment], alerts: list[dict], sessions: list[dict],
              daily_exercise_min: list[float] | None = None) -> ExerciseGuidanceV1:
    """Conservative rule-based readiness. Abstains when there is not enough evidence.

    This is an adapter: a dedicated exercise AI model can replace `recommend` later
    by registering a plug-in with category "exercise" and returning the same contract.
    """
    by_cat: dict[str, list[Assessment]] = {}
    for a in assessments:
        if a.status == "ok":
            by_cat.setdefault(a.category, []).append(a)
    fatigue = (by_cat.get("fatigue") or [None])[0]
    sleep = (by_cat.get("sleep_hrv") or [None])[0]
    anomalies = [a for cat in ("anomaly", "illness") for a in by_cat.get(cat, []) if a.severity in ("caution", "warning")]
    relevant_alerts = [al for al in alerts if al.get("severity") in ("warning", "caution")
                       and al.get("category") in ("cardiovascular", "anomaly", "vitals", "fatigue", "sleep", "illness")]
    rationale: list[str] = []
    readiness = "insufficient_data"
    if any(al.get("severity") == "warning" for al in relevant_alerts) or any(a.severity == "warning" for a in anomalies):
        readiness = "rest_and_recheck"
        rationale.append("A warning-level health alert or anomaly is active.")
    elif anomalies or any(al.get("severity") == "caution" for al in relevant_alerts):
        readiness = "reduce_intensity"
        rationale.append("A caution-level anomaly or alert is active.")
    elif fatigue is not None:
        high = fatigue.severity in ("caution", "warning")
        readiness = "reduce_intensity" if high else "proceed"
        rationale.append(f"Fatigue estimate: {fatigue.score_label or fatigue.score} ({fatigue.model_id}).")
    else:
        rationale.append("No recent fatigue estimate and no active alerts: not enough evidence to advise.")
    text = {
        "proceed": "Proceed with the planned session; stop if you feel unwell.",
        "reduce_intensity": "Consider a lighter session (lower intensity or shorter) and re-check how you feel.",
        "rest_and_recheck": "Consider postponing intense exercise and check in with the crew medical officer.",
        "insufficient_data": "No recommendation: complete a fatigue check-in or sync wearable data first.",
    }[readiness]
    return ExerciseGuidanceV1(
        astronaut_id=astronaut_id, generated_at=datetime.now(timezone.utc), readiness=readiness, recommendation=text,
        rationale=rationale, fatigue=_summ(fatigue) if fatigue else None, sleep=_summ(sleep) if sleep else None,
        anomalies=[_summ(a) for a in anomalies],
        active_alerts=[{k: al.get(k) for k in ("id", "severity", "category", "title")} for al in relevant_alerts],
        adherence_14d=adherence(sessions, daily_exercise_min),
        source_models=sorted({a.model_id for a in assessments if a.status == "ok"}),
        limitations=["Conservative rule-based adapter, not an exercise prescription.",
                     "Models feeding it are Earth-trained or simulated, not validated on astronauts."])


def export_schemas() -> list[Path]:
    CONTRACTS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for cls, name in [(ExerciseSessionSummaryV1, "exercise_session_summary.v1.json"),
                      (ExerciseGuidanceV1, "exercise_guidance.v1.json")]:
        p = CONTRACTS_DIR / name
        p.write_text(json.dumps(cls.model_json_schema(), indent=1), encoding="utf-8")
        out.append(p)
    from ai.core.types import Assessment as A
    p = CONTRACTS_DIR / "ai_assessment.v1.json"
    p.write_text(json.dumps(A.model_json_schema(), indent=1), encoding="utf-8")
    out.append(p)
    return out


if __name__ == "__main__":
    for p in export_schemas():
        print("wrote", p)
