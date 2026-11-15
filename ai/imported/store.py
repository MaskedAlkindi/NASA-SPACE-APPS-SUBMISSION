"""Read and write imported model sets.

A set is one JSON file. The server turns it into a manifest plus rules.json.
The Python that runs it is the built-in rule plug-in, never code from the file.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

FORMAT = "health01-model-set"
ENTRYPOINT = "ai.imported.rule:ImportedRule"

SAMPLE = {
    "format": FORMAT,
    "id": "fatigue_buildup",
    "name": "Fatigue build-up",
    "version": "1.0.0",
    "description": "Compares today's fatigue check-in with this astronaut's own earlier days. A climb files an alert.",
    "metric": "fatigue_score",
    "direction": "above",
    "mode": "baseline_z",
    "info_z": 1.0,
    "caution_z": 1.5,
    "warning_z": 2.5,
    "min_days": 4,
    "window_days": 14,
    "emit_alerts": True,
    "min_severity": "caution",
}


def import_dir() -> Path:
    raw = os.getenv("HMT_AI_IMPORT_DIR")
    if raw:
        path = Path(raw)
    else:
        path = Path(__file__).resolve().parents[2] / "data" / "imported_models"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _num(value, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number") from None
    if number != number or abs(number) > 1_000_000:  # NaN, or an unbounded line
        raise ValueError(f"{name} is out of range")
    return number


def normalize(body: dict) -> dict:
    """Check a downloaded or uploaded set and return the stored shape."""
    if not isinstance(body, dict):
        raise ValueError("the model file must be a JSON object")
    if body.get("format") not in (None, FORMAT):
        raise ValueError(f"format must be {FORMAT}")
    model_id = str(body.get("id") or "").strip()
    if not model_id.replace("_", "a").replace("-", "a").isalnum() or not model_id[0].isalpha() or len(model_id) > 40:
        raise ValueError("id must be a short name like fatigue_buildup")
    from app.schemas.metrics import METRICS

    metric = str(body.get("metric") or "")
    spec = METRICS.get(metric)
    if spec is None or not spec.per_astronaut:
        known = ", ".join(sorted(m.name for m in METRICS.values() if m.per_astronaut))
        raise ValueError(f"metric must be one of: {known}")
    direction = body.get("direction") or "above"
    mode = body.get("mode") or "baseline_z"
    if direction not in ("above", "below"):
        raise ValueError("direction must be above or below")
    if mode not in ("baseline_z", "value"):
        raise ValueError("mode must be baseline_z or value")
    min_days = int(body.get("min_days") or (4 if mode == "baseline_z" else 1))
    window_days = int(body.get("window_days") or 14)
    if not 1 <= min_days <= 60 or not 3 <= window_days <= 90:
        raise ValueError("min_days must be 1–60 and window_days 3–90")
    severity = body.get("min_severity") or "caution"
    if severity not in ("info", "caution", "warning"):
        raise ValueError("min_severity must be info, caution, or warning")
    rules: dict = {
        "metric": metric,
        "unit": spec.unit,
        "direction": direction,
        "mode": mode,
        "min_days": min_days,
        "window_days": window_days,
    }
    if mode == "baseline_z":
        info_z = _num(body.get("info_z", 1.0), "info_z")
        caution_z = _num(body.get("caution_z", 1.5), "caution_z")
        warning_z = _num(body.get("warning_z", 2.5), "warning_z")
        if not 0 <= info_z <= caution_z <= warning_z:
            raise ValueError("need 0 ≤ info_z ≤ caution_z ≤ warning_z")
        rules.update(info_z=info_z, caution_z=caution_z, warning_z=warning_z)
    else:
        if body.get("caution_value") is None:
            raise ValueError("value mode needs caution_value")
        caution_value = _num(body["caution_value"], "caution_value")
        warning_value = None if body.get("warning_value") is None else _num(body["warning_value"], "warning_value")
        if warning_value is not None:
            if direction == "above" and warning_value < caution_value:
                raise ValueError("for an above line, warning_value must be at least caution_value")
            if direction == "below" and warning_value > caution_value:
                raise ValueError("for a below line, warning_value must be at most caution_value")
        rules.update(caution_value=caution_value, warning_value=warning_value)
    name = str(body.get("name") or f"Imported {spec.label}").strip()[:80]
    if not name:
        raise ValueError("name is required")
    description = str(body.get("description") or f"Imported rule on {spec.label}. A crossing files an alert.").strip()[:400]
    return {
        "id": model_id,
        "name": name,
        "version": str(body.get("version") or "1.0.0")[:20],
        "description": description,
        "category": spec.domain,
        "metric_label": spec.label,
        "emit_alerts": bool(body.get("emit_alerts", True)),
        "min_severity": severity,
        "rules": rules,
    }


def manifest_for(spec: dict) -> dict:
    rules = spec["rules"]
    thresholds = {k: v for k, v in rules.items() if isinstance(v, (int, float)) and k != "min_days" and k != "window_days"}
    return {
        "id": spec["id"],
        "name": spec["name"],
        "version": spec["version"],
        "category": spec["category"],
        "description": spec["description"],
        "intended_use": "Watch one measurement against this astronaut's own days, and file an alert when it crosses the line in this set.",
        "not_intended_for": "Clinical diagnosis or treatment decisions.",
        "entrypoint": ENTRYPOINT,
        "inputs": [{
            "metric": rules["metric"],
            "unit": rules["unit"],
            "required": True,
            "min_days": rules["min_days"],
            "max_staleness_days": 14,
        }],
        "outputs": {"score": "the z-score or the reading that was compared"},
        "supported_indicators": [spec["metric_label"]],
        "datasets": [{
            "name": "Imported model set",
            "source": "uploaded in the demo",
            "license": "imported by the user",
            "population": "this crew's own recorded days",
            "astronaut_data": False,
            "simulated": False,
        }],
        "evidence_level": "rule_based",
        "validated_on_astronauts": False,
        "status": "research_prototype",
        "artifact": None,
        "report": None,
        "enabled_by_default": True,
        "execution": {"environments": ["server", "desktop"], "provider": "local", "timeout_s": 5, "memory_mb": 50, "requires": []},
        "alerting": {
            "emit_alerts": spec["emit_alerts"],
            "min_severity": spec["min_severity"],
            "cooldown_hours": 24,
            "thresholds": thresholds,
        },
    }


def is_imported(folder: Path) -> bool:
    try:
        folder.resolve().relative_to(import_dir().resolve())
        return True
    except ValueError:
        return False


def save_set(body: dict) -> dict:
    spec = normalize(body)
    root = import_dir().resolve()
    folder = (root / spec["id"]).resolve()
    if root not in folder.parents:
        raise ValueError("that id cannot be saved")
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    (folder / "rules.json").write_text(json.dumps(spec["rules"], indent=2), encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps(manifest_for(spec), indent=2), encoding="utf-8")
    return spec


def delete_set(model_id: str) -> None:
    root = import_dir().resolve()
    folder = (root / model_id).resolve()
    if root not in folder.parents or not folder.is_dir():
        raise ValueError("that model was not imported")
    shutil.rmtree(folder)
