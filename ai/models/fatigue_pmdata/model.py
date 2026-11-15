"""Fatigue / stress from wearable signals, trained on PMData self-reports (Earth research model).

Leave-one-subject-out AUC is low (~0.55, see report.json): treat the output as a weak hint
and a prompt to complete a fatigue check-in, never as a measurement.
"""
from __future__ import annotations

import joblib
import numpy as np

from ai.core.plugin import ModelPlugin
from ai.core.types import Assessment
from ai.preprocessing.daily_features import BASE_METRICS, FEATURES, build


class FatiguePMData(ModelPlugin):
    def _load(self):
        self.bundle = joblib.load(self.artifact_path())

    def _unload(self):
        self.bundle = None

    def _predict(self, view, quality):
        daily = view.daily(BASE_METRICS, days=45)
        feats = build(daily)
        row = feats.iloc[[-1]][FEATURES]
        n_avail = int(row.notna().sum(axis=1).iloc[0])
        if n_avail < 4:
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data",
                                          f"Only {n_avail} of {len(FEATURES)} features available today.")
        p_tired = float(self.bundle["tired"]["model"].predict_proba(row)[0, 1])
        p_stress = float(self.bundle["stressed"]["model"].predict_proba(row)[0, 1])
        auc_t = self.bundle["tired"]["loso"]["auc_pooled"]
        auc_s = self.bundle["stressed"]["loso"]["auc_pooled"]
        th = self.manifest.alerting.thresholds
        label = "more tired than usual: possible" if p_tired >= th.get("info_probability", 0.6) else \
                "no clear sign of extra tiredness" if p_tired < 0.4 else "uncertain"
        sev = "info" if p_tired >= th.get("info_probability", 0.6) else "none"     # never above info: weak model
        missing = [f for f in FEATURES if np.isnan(row[f].iloc[0])]
        return Assessment(
            astronaut_id=view.astronaut_id, model_id=self.manifest.id, model_version=self.manifest.version, status="ok",
            category=self.manifest.category, severity=sev, score=round(p_tired, 3), score_label=label,
            scale="probability of a 'more tired than normal' day (PMData definition)",
            uncertainty={"model_auc_loso": auc_t, "note": "low discrimination; a check-in is more informative"},
            calibration=f"Leave-one-subject-out AUC {auc_t} (tired), {auc_s} (stressed) on 16 PMData participants.",
            data_as_of=str(feats["date"].iloc[-1].date()),
            explanation=(f"Based on resting HR, sleep and activity relative to your own baseline, the model rates the chance "
                         f"of a more-tired-than-usual day at {p_tired:.0%}. This model is weak (AUC {auc_t}); your own "
                         f"check-in is the better guide."),
            recommendation="Complete a fatigue check-in so the estimate can be checked against how you actually feel.",
            data_quality={"features_available": n_avail, "features_missing": missing},
            limitations=["Trained on 16 healthy Earth-based adults (PMData); not validated on astronauts.",
                         "Low accuracy from wearables alone; self-reported fatigue was a stronger predictor.",
                         "PMData uses a different fatigue scale from the app's Samn-Perelli check-in."],
            evidence_level=self.manifest.evidence_level,
            outputs={"p_more_tired_than_usual": round(p_tired, 3), "p_more_stressed_than_usual": round(p_stress, 3),
                     "features": {k: (None if np.isnan(v) else round(float(v), 3)) for k, v in row.iloc[0].items()}})
