"""Assessment -> standard alert event.

Every model emits `Assessment`s. This adapter decides which become alert events,
using the model's AlertPolicy (and per-model threshold overrides), and produces a
de-duplication key so the alert system notifies once per model/astronaut/category
within the cooldown window. Informational insights are kept apart from concerns.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ai.core.types import AlertPolicy, Assessment, ModelManifest

SEVERITY_RANK = {"none": 0, "info": 1, "caution": 2, "warning": 3}
EVIDENCE_NOTE = {
    "spaceflight": "Based on spaceflight evidence.",
    "earth_research": "Research model trained/evaluated on Earth-based data, not validated on astronauts.",
    "simulation": "Demonstration model trained on simulated data.",
    "rule_based": "Transparent rule based on published reference values.",
}
EVENT_SCHEMA_VERSION = "ai.alert_event.v1"


def to_event(a: Assessment, manifest: ModelManifest, policy: AlertPolicy | None = None) -> dict[str, Any] | None:
    """Return a standard alert event, or None if the assessment should not alert."""
    policy = policy or manifest.alerting
    if a.status != "ok" or not policy.emit_alerts:
        return None
    if SEVERITY_RANK[a.severity] < SEVERITY_RANK["info"]:
        return None
    kind = "concern" if SEVERITY_RANK[a.severity] >= SEVERITY_RANK[policy.min_severity] else "insight"
    bucket = int(a.assessed_at.timestamp() // (policy.cooldown_hours * 3600))
    return {
        "schema": EVENT_SCHEMA_VERSION,
        "astronaut_id": a.astronaut_id, "model_id": a.model_id, "model_version": a.model_version,
        "assessed_at": a.assessed_at.isoformat(), "data_as_of": a.data_as_of,
        "risk_category": a.category, "severity": a.severity, "kind": kind,
        "score": a.score, "score_label": a.score_label, "scale": a.scale, "calibration": a.calibration,
        "uncertainty": a.uncertainty,
        "explanation": a.explanation,
        "contributing": [c.model_dump() for c in a.contributing],
        "recommended_follow_up": a.recommendation,
        "data_quality": a.data_quality, "limitations": a.limitations,
        "evidence_level": a.evidence_level, "evidence_note": EVIDENCE_NOTE[a.evidence_level],
        "not_a_diagnosis": True,
        "dedupe_key": f"ai:{a.model_id}:{a.astronaut_id}:{a.category}:{a.severity}:{bucket}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
