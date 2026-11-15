"""One rule, read from rules.json. Used by every imported model set."""
from __future__ import annotations

import json

import numpy as np

from ai.core.plugin import ModelPlugin
from ai.core.types import Assessment, Contribution
from ai.preprocessing.signals import causal_baseline


class ImportedRule(ModelPlugin):
    def _load(self) -> None:
        self.rules = json.loads((self.folder / "rules.json").read_text(encoding="utf-8"))

    def _severity(self, score: float) -> str:
        rules = self.rules
        direction = rules["direction"]
        if rules["mode"] == "baseline_z":
            mag = score if direction == "above" else -score
            if mag >= rules["warning_z"]:
                return "warning"
            if mag >= rules["caution_z"]:
                return "caution"
            if mag >= rules["info_z"]:
                return "info"
            return "none"
        caution, warning = rules["caution_value"], rules.get("warning_value")
        if direction == "above":
            if warning is not None and score >= warning:
                return "warning"
            if score >= caution:
                return "caution"
            return "none"
        if warning is not None and score <= warning:
            return "warning"
        if score <= caution:
            return "caution"
        return "none"

    def _predict(self, view, quality):
        rules = self.rules
        metric = rules["metric"]
        days = max(rules["window_days"] + rules["min_days"], 30)
        frame = view.daily([metric], days=days).dropna(subset=[metric])
        if len(frame) < rules["min_days"]:
            return Assessment.unavailable(
                view.astronaut_id, self.manifest, "insufficient_data",
                f"Needs {rules['min_days']} days of {metric} (have {len(frame)}).",
            )
        last = frame.iloc[-1]
        value = float(last[metric])
        baseline = None
        score = value
        scale = rules["unit"]
        if rules["mode"] == "baseline_z":
            series = frame.set_index("date")[metric]
            base = causal_baseline(series, window=rules["window_days"], gap=1, min_periods=max(3, rules["min_days"] - 1))
            z = base["z"].iloc[-1]
            baseline = base["base_median"].iloc[-1]
            if np.isnan(z) or np.isnan(baseline):
                return Assessment.unavailable(
                    view.astronaut_id, self.manifest, "insufficient_data",
                    "Not enough earlier days yet to compare this astronaut with themselves.",
                )
            score = float(z)
            baseline = float(baseline)
            scale = "robust z vs own earlier days"
            label = "within usual range"
            if self._severity(score) == "warning":
                label = "well above usual" if rules["direction"] == "above" else "well below usual"
            elif self._severity(score) in ("caution", "info"):
                label = "above usual" if rules["direction"] == "above" else "below usual"
            explanation = f"{metric.replace('_', ' ')} {value:g} {rules['unit']} vs your usual {baseline:g} (z = {score:.1f})."
        else:
            line = rules["caution_value"]
            label = "crosses the imported line" if self._severity(score) != "none" else "inside the imported line"
            explanation = f"{metric.replace('_', ' ')} is {value:g} {rules['unit']}. The imported line is {line:g}."
        severity = self._severity(score)
        return Assessment(
            astronaut_id=view.astronaut_id, model_id=self.manifest.id, model_version=self.manifest.version,
            status="ok", category=self.manifest.category, severity=severity, score=round(score, 2),
            score_label=label, scale=scale, data_as_of=str(last["date"].date()) if hasattr(last["date"], "date") else str(last["date"])[:10],
            explanation=explanation + " This reading comes from the model set you imported.",
            contributing=[Contribution(metric=metric, value=value, unit=rules["unit"], baseline=baseline,
                                       deviation=round(score, 2) if rules["mode"] == "baseline_z" else None,
                                       note="imported model set")],
            recommendation=("An alert is filed with the others. It is not a diagnosis. A person still decides."
                            if severity != "none" else ""),
            limitations=["Imported rule, not validated on astronauts.",
                         "It compares this astronaut with their own earlier days, or with the line in the file."],
            evidence_level="rule_based",
            outputs={"mode": rules["mode"], "direction": rules["direction"], "value": value},
        )
