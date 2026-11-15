"""Sleep & HRV recovery indicators (transparent rules; processing verified on MMASH)."""
from __future__ import annotations

import numpy as np

from ai.core.plugin import ModelPlugin
from ai.core.types import Assessment, Contribution
from ai.preprocessing.signals import causal_baseline


class SleepHRV(ModelPlugin):
    def _predict(self, view, quality):
        th = self.manifest.alerting.thresholds
        d = view.daily(["sleep_duration", "sleep_midpoint", "hrv_sdnn", "hrv_rmssd"], days=45)
        d = d.set_index("date").asfreq("D").reset_index()
        sl = d["sleep_duration"]
        if sl.notna().sum() < 7:
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data", "Needs 7 nights of sleep data.")
        hrv_col = "hrv_sdnn" if d["hrv_sdnn"].notna().sum() >= d["hrv_rmssd"].notna().sum() else "hrv_rmssd"
        out, contrib, flags = {}, [], []
        base_sleep = float(sl.iloc[:-1].tail(28).median())
        debt7 = float(np.clip(base_sleep - sl.tail(7), 0, None).sum())
        out["sleep_debt_7d_h_vs_own_median"] = round(debt7, 1)
        mid = d["sleep_midpoint"].dropna().tail(7)
        out["sleep_timing_sd_7d_h"] = round(float(mid.std()), 2) if len(mid) >= 4 else None
        contrib.append(Contribution(metric="sleep_duration", value=float(sl.dropna().iloc[-1]), unit="h", baseline=round(base_sleep, 2),
                                    note=f"7-night debt {debt7:.1f} h"))
        if debt7 >= th.get("sleep_debt_h", 5.0):
            flags.append(f"{debt7:.1f} h less sleep than your usual over 7 nights")
        if out["sleep_timing_sd_7d_h"] is not None and out["sleep_timing_sd_7d_h"] >= th.get("timing_sd_h", 1.0):
            flags.append(f"irregular sleep timing (±{out['sleep_timing_sd_7d_h']} h)")
        if d[hrv_col].notna().sum() >= 10:
            b = causal_baseline(d[hrv_col], window=28, gap=1, min_periods=7)
            last = d.index[d[hrv_col].notna()][-1]
            z = b["z"].iloc[last]
            if not np.isnan(z):
                out["hrv_z"] = round(float(z), 2)
                out["hrv_metric"] = hrv_col
                contrib.append(Contribution(metric=hrv_col, value=float(d[hrv_col].iloc[last]), unit="ms",
                                            baseline=round(float(b["base_median"].iloc[last]), 1), deviation=round(float(z), 2)))
                if z <= th.get("hrv_low_z", -2.0):
                    flags.append(f"HRV well below your baseline (z = {z:.1f})")
        sev = "info" if flags else "none"
        recovery = "reduced" if len(flags) >= 2 else "watch" if flags else "normal"
        out["recovery_indicator"] = recovery
        return Assessment(
            astronaut_id=view.astronaut_id, model_id=self.manifest.id, model_version=self.manifest.version, status="ok",
            category=self.manifest.category, severity=sev, score_label=f"recovery: {recovery}",
            scale="rule-based indicator (normal / watch / reduced)", data_as_of=str(d["date"].iloc[-1].date()),
            calibration="Rules, not a trained model. HR/HRV and sleep processing verified on MMASH (see report.json).",
            explanation=("Recovery signals: " + "; ".join(flags) + ".") if flags else "Sleep and HRV are within your usual pattern.",
            contributing=contrib,
            recommendation=("Protect the next sleep period and keep sleep timing regular where operations allow." if flags else ""),
            limitations=["Transparent rules based on personal baselines; thresholds are configurable defaults.",
                         "SDNN (Apple) and RMSSD (Health Connect) are different HRV measures and are never mixed."],
            evidence_level=self.manifest.evidence_level, outputs=out)
