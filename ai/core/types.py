"""Core contracts of the AI engine. Every model plug-in speaks these types.

Nothing in here knows about a specific model, the database or the web API.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

EvidenceLevel = Literal["spaceflight", "earth_research", "simulation", "rule_based"]
Severity = Literal["none", "info", "caution", "warning"]
AssessmentStatus = Literal["ok", "insufficient_data", "abstained", "error", "disabled"]


class FeatureSpec(BaseModel):
    """One input a model needs. `metric` is a canonical metric name from the health data layer."""
    metric: str
    unit: str
    kind: Literal["daily", "series", "event", "profile"] = "daily"
    required: bool = True
    min_days: int = 1                     # how many days of history are needed
    max_staleness_days: float = 3.0       # newest value must be at most this old
    description: str = ""


class DatasetRef(BaseModel):
    name: str
    source: str
    license: str
    citation: str = ""
    population: str = ""
    astronaut_data: bool = False
    simulated: bool = False
    provenance_file: str = ""             # data/external/<name>/PROVENANCE.json when downloaded


class ExecutionSpec(BaseModel):
    environments: list[Literal["server", "desktop", "device"]] = ["server", "desktop"]
    provider: str = "local"               # local | http (see ai.inference.providers)
    timeout_s: float = 10.0
    memory_mb: int = 200
    requires: list[str] = []              # python packages needed at inference time


class AlertPolicy(BaseModel):
    emit_alerts: bool = True
    min_severity: Severity = "caution"    # assessments below this stay informational
    cooldown_hours: float = 24.0
    thresholds: dict[str, float] = {}     # model-specific, overridable in model state


class ModelManifest(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_\-]+$")
    name: str
    version: str
    category: str                         # fatigue | anomaly | glucose | sleep_hrv | orthostatic | forecast | exercise | ...
    description: str
    intended_use: str
    not_intended_for: str = "Clinical diagnosis or treatment decisions."
    entrypoint: str                       # "package.module:ClassName"
    inputs: list[FeatureSpec]
    outputs: dict[str, Any]               # JSON-schema-like description of Assessment.outputs
    supported_indicators: list[str] = []
    datasets: list[DatasetRef] = []
    evidence_level: EvidenceLevel
    validated_on_astronauts: bool = False
    status: Literal["ready", "research_prototype", "pending_data", "deprecated"] = "ready"
    artifact: str | None = None           # path relative to the model folder
    report: str | None = "report.json"    # evaluation report, relative to the model folder
    enabled_by_default: bool = True
    execution: ExecutionSpec = ExecutionSpec()
    alerting: AlertPolicy = AlertPolicy()


class Contribution(BaseModel):
    metric: str
    value: float | None = None
    unit: str = ""
    baseline: float | None = None
    deviation: float | None = None        # z-score or relative change, see `note`
    note: str = ""


class Assessment(BaseModel):
    astronaut_id: str
    model_id: str
    model_version: str
    assessed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_as_of: str | None = None
    status: AssessmentStatus
    category: str
    severity: Severity = "none"
    score: float | None = None
    score_label: str = ""
    scale: str = ""
    uncertainty: dict[str, Any] = {}      # e.g. {"interval_80": [lo, hi], "method": "..."}
    calibration: str = ""                 # how well scores are calibrated, in words
    explanation: str = ""
    contributing: list[Contribution] = []
    recommendation: str = ""
    data_quality: dict[str, Any] = {}     # coverage, missing, stale
    limitations: list[str] = []
    evidence_level: EvidenceLevel = "simulation"
    outputs: dict[str, Any] = {}

    @classmethod
    def unavailable(cls, astronaut_id: str, m: ModelManifest, status: AssessmentStatus, why: str, **quality) -> "Assessment":
        return cls(astronaut_id=astronaut_id, model_id=m.id, model_version=m.version, status=status, category=m.category,
                   explanation=why, data_quality=quality, evidence_level=m.evidence_level)
