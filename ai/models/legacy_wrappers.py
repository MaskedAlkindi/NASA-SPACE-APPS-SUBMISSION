"""Plug-in wrappers around the original ml/ models (simulation-trained). Kept for backward compatibility:
the existing /predictions endpoint and alert rules still use ml/ directly; these wrappers expose the
same models through the AI registry so they can be listed, enabled/disabled and compared."""
from __future__ import annotations

import json

from ai.core.plugin import ModelPlugin
from ai.core.types import Assessment, Contribution


def _ml_report(key: str) -> dict | None:
    from ml.models import artifacts
    rep = artifacts.load_json("metrics_report.json") or {}
    return rep.get(key)


class LegacyAnomaly(ModelPlugin):
    def _load(self):
        from ml.models.anomaly import AnomalyDetector
        self.det = AnomalyDetector()
        if not self.det.available:
            raise RuntimeError("ml anomaly artifact missing (run python -m ml.training.train_all)")

    def report(self):
        from ml.models import artifacts
        return _ml_report(artifacts.ANOMALY_VERSION)

    def _predict(self, view, quality):
        d = view.daily(["resting_heart_rate", "hrv_sdnn", "sleep_duration", "steps"], days=60)
        r = self.det.latest(d)
        if not r or r["status"] != "scored":
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data", "Personal baseline not ready.")
        sev = "caution" if r["is_anomaly"] else "none"
        return Assessment(
            astronaut_id=view.astronaut_id, model_id=self.manifest.id, model_version=self.manifest.version, status="ok",
            category=self.manifest.category, severity=sev, score=r["score"], score_label="unusual" if r["is_anomaly"] else "usual",
            scale="Isolation Forest anomaly score", data_as_of=r["date"],
            calibration=f"Simulated evaluation only. On real Stanford smartwatch data: see illness_rhr report (legacy_iforest rows).",
            explanation="Unusual combination of measurements vs your baseline." if r["is_anomaly"] else "Within normal variation.",
            contributing=[Contribution(metric=c["metric"], value=c["value"], baseline=c["baseline_median"], deviation=c["z"]) for c in r["contributors"][:4]],
            limitations=["Trained on simulated data."], evidence_level="simulation",
            outputs={"percentile": r.get("score_percentile"), "missing": r.get("missing")})


class LegacyFatigueSim(ModelPlugin):
    def _load(self):
        from ml.models.fatigue import FatigueModel
        self.m = FatigueModel()
        if not self.m.available:
            raise RuntimeError("ml fatigue artifact missing")

    def report(self):
        from ml.models import artifacts
        return _ml_report(artifacts.FATIGUE_VERSION)

    def _predict(self, view, quality):
        d = view.daily(["sleep_duration", "sleep_midpoint", "sleep_efficiency", "exercise_minutes", "workload_tlx", "fatigue_score"], days=14)
        e = self.m.estimate_latest(d)
        if not e or e.get("status") != "estimated":
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data", "Not enough inputs.")
        return Assessment(
            astronaut_id=view.astronaut_id, model_id=self.manifest.id, model_version=self.manifest.version, status="ok",
            category=self.manifest.category, severity="none", score=e["fatigue_estimate"], score_label=e["category"],
            scale=e["scale"], uncertainty={"interval_80": e["interval_80"]}, data_as_of=e["date"],
            explanation="Simulation-trained fatigue estimate.", limitations=["Synthetic labels only."], evidence_level="simulation",
            outputs={"inputs": e["inputs"], "missing": e["missing"]})


class LegacyForecast(ModelPlugin):
    def _load(self):
        from ml.models.forecast import TrendForecaster
        self.f = TrendForecaster()

    def report(self):
        from ml.models import artifacts
        return _ml_report(artifacts.FORECAST_VERSION)

    def _predict(self, view, quality):
        d = view.daily(["resting_heart_rate", "sleep_duration", "hrv_sdnn"], days=60)
        series = [self.f.forecast(d, m) for m in ("resting_heart_rate", "sleep_duration", "hrv_sdnn")]
        ok = [s for s in series if s.get("status") == "forecast"]
        if not ok:
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data", "Needs 10 days of history.")
        return Assessment(
            astronaut_id=view.astronaut_id, model_id=self.manifest.id, model_version=self.manifest.version, status="ok",
            category=self.manifest.category, severity="none", scale="7-day forecasts with 80% intervals",
            explanation="; ".join(f"{s['metric']}: {s['trend_direction']}" for s in ok), evidence_level="simulation",
            limitations=["Parameters chosen on simulated backtests."], outputs={"series": json.loads(json.dumps(series, default=str))})
