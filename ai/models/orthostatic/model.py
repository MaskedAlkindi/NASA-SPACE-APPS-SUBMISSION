"""Orthostatic response features from a stand test (research prototype, disabled by default).

Expects a `stand_test` series whose rows carry beat-level data in `value_json`:
  {"t": [s...], "sbp": [mmHg...], "dbp": [mmHg...], "hr": [bpm...], "stand_t": s}
No such device feed exists in the app yet, so the model normally reports insufficient data.
"""
from __future__ import annotations

import numpy as np

from ai.core.plugin import ModelPlugin
from ai.core.types import Assessment, Contribution
from ai.preprocessing.orthostatic import response


class Orthostatic(ModelPlugin):
    def _predict(self, view, quality):
        s = view.series("stand_test", days=30)
        if s is None or len(s) == 0 or "value_json" not in s:
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data", "No stand-test recording available.")
        rec = s["value_json"].iloc[-1] or {}
        try:
            beats = {k: np.asarray(rec[k], float) for k in ("t", "sbp", "dbp", "hr")}
            res = response(beats, float(rec["stand_t"]))
        except (KeyError, TypeError, ValueError) as e:
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data", f"Stand-test record unusable: {e}")
        if not res.get("valid"):
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data", "Not enough clean beats around standing.")
        flag = res["oh_criterion"] or res["hr_rise_criterion"]
        return Assessment(
            astronaut_id=view.astronaut_id, model_id=self.manifest.id, model_version=self.manifest.version, status="ok",
            category=self.manifest.category, severity="info" if flag else "none", score=res["delta_sbp"],
            score_label="consensus criterion met" if flag else "no consensus criterion met", scale="SBP change, mmHg",
            explanation=(f"Standing changed SBP by {res['delta_sbp']:+} mmHg, DBP by {res['delta_dbp']:+} mmHg and HR by "
                         f"{res['delta_hr']:+} bpm (peak +{res['hr_peak_rise']} bpm)."),
            contributing=[Contribution(metric="blood_pressure_systolic", value=res["delta_sbp"], unit="mmHg", note="sustained change")],
            recommendation="Research prototype: share the result with the flight surgeon if you felt light-headed." if flag else "",
            limitations=["Research prototype; features verified only moderately against published values (see report.json).",
                         "Earth-based (older adults); says nothing about tolerance of landing or re-entry."],
            evidence_level=self.manifest.evidence_level, outputs=res)
