"""Template plug-in. Copy this folder into ai/models/<your_id>/ (or a folder listed in HMT_AI_MODEL_PATHS),
rename the class, update manifest.json (id + entrypoint), and implement _predict."""
from ai.core.plugin import ModelPlugin
from ai.core.types import Assessment, Contribution


class MyNewModel(ModelPlugin):
    def _load(self):
        # Load artifacts here, e.g. joblib.load(self.artifact_path()). Called lazily on first use.
        pass

    def _predict(self, view, quality):
        # `view` is a HealthDataView for ONE astronaut; inputs were already checked for presence, units and staleness.
        d = view.daily(["resting_heart_rate"], days=30).dropna()
        value = float(d["resting_heart_rate"].iloc[-1])
        return Assessment(
            astronaut_id=view.astronaut_id, model_id=self.manifest.id, model_version=self.manifest.version,
            status="ok", category=self.manifest.category, severity="none", score=value, scale="bpm",
            explanation=f"Latest resting heart rate {value:.0f} bpm.",
            contributing=[Contribution(metric="resting_heart_rate", value=value, unit="bpm")],
            limitations=["Template example."], evidence_level=self.manifest.evidence_level, outputs={"value": value})
