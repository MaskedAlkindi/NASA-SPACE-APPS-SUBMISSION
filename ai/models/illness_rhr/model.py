"""Illness-related physiological change: resting heart rate vs the astronaut's own baseline.

Evaluated on the Stanford smartwatch illness data (see report.json). It flags a change that
often accompanies illness onset; it does not diagnose illness.
"""
from __future__ import annotations

import numpy as np

from ai.core.plugin import ModelPlugin
from ai.core.types import Assessment, Contribution
from ai.preprocessing.signals import causal_baseline


class IllnessRHR(ModelPlugin):
    def _predict(self, view, quality):
        th = {**self.manifest.alerting.thresholds}
        d = view.daily(["resting_heart_rate"], days=60).dropna(subset=["resting_heart_rate"])
        if len(d) < 15:
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data",
                                          f"Needs 15 days of resting heart rate for a personal baseline (have {len(d)}).")
        d = d.set_index("date").asfreq("D").reset_index()
        b = causal_baseline(d["resting_heart_rate"], window=28, gap=1, min_periods=14)
        last = d.index[d["resting_heart_rate"].notna()][-1]
        z, base, val = b["z"].iloc[last], b["base_median"].iloc[last], d["resting_heart_rate"].iloc[last]
        if np.isnan(z):
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data", "Baseline not yet stable.")
        prev_z = b["z"].iloc[last - 1] if last >= 1 else np.nan
        sev = "none"
        if z >= th.get("caution_z", 3.0):
            sev = "caution"
        elif z >= th.get("info_z", 2.5):
            sev = "info"
        rep = self.report() or {}
        held = rep.get("held_out_half") or {}
        calib = (f"Stanford smartwatch data, held-out participants: sensitivity {held.get('sensitivity')}, day-level "
                 f"specificity {held.get('specificity_day')}, {held.get('false_alert_episodes_per_30_healthy_days')} false-alert "
                 f"episodes per 30 healthy days (n={held.get('events_evaluable')} illness events)." if held else "")
        rising = bool(not np.isnan(prev_z) and prev_z >= th.get("info_z", 2.5))
        return Assessment(
            astronaut_id=view.astronaut_id, model_id=self.manifest.id, model_version=self.manifest.version, status="ok",
            category=self.manifest.category, severity=sev, score=round(float(z), 2), scale="robust z vs own 28-day baseline",
            score_label=("well above usual" if z >= 3 else "above usual" if z >= 2 else "within usual range"),
            data_as_of=str(d["date"].iloc[last].date()), calibration=calib,
            explanation=(f"Resting heart rate {val:.0f} bpm vs your usual {base:.0f} bpm (z = {z:.1f})."
                         + (" It was also raised the previous day." if rising and sev != "none" else "")),
            contributing=[Contribution(metric="resting_heart_rate", value=float(val), unit="bpm", baseline=float(base),
                                       deviation=round(float(z), 2), note="robust z-score")],
            recommendation=("Raised resting heart rate can come before symptoms of illness, but also follows poor sleep, "
                            "stress, dehydration or hard exercise. Note how you feel, re-check tomorrow morning, and tell the "
                            "crew medical officer if it persists or you feel unwell." if sev != "none" else ""),
            limitations=["Earth-based evaluation (smartwatch users), not validated on astronauts.",
                         "Detects a physiological change, not a specific illness.",
                         "Few illness events in the evaluation; sensitivity estimates are uncertain."],
            evidence_level=self.manifest.evidence_level,
            outputs={"z": round(float(z), 2), "resting_hr": float(val), "baseline_rhr": float(base), "previous_day_z":
                     None if np.isnan(prev_z) else round(float(prev_z), 2)})
