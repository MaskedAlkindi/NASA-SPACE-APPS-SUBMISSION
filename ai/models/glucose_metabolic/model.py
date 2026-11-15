"""Glucose & metabolic monitoring (CGMacros research model + standard calculations).

What it does depends on the data available - it never invents missing measurements:
  * daily fasting glucose  -> personal trend, variability and days outside the lab reference range
  * fasting insulin within 2 days of a fasting glucose -> HOMA-IR (Matthews 1985)
  * CGM-like data (>= 3 days with >= 48 readings/day) -> CGM metrics and a research
    insulin-resistance flag (leave-one-subject-out AUC ~0.8 on 45 CGMacros adults)
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd

from ai.core.plugin import ModelPlugin
from ai.core.types import Assessment, Contribution
from ai.preprocessing.signals import cgm_metrics, homa_ir

REF = (65.0, 99.0)   # fasting glucose reference range published in NASA OSD-575 (Inspiration4) lab file


class GlucoseMetabolic(ModelPlugin):
    def _load(self):
        self.bundle = joblib.load(self.artifact_path())

    def _predict(self, view, quality):
        th = self.manifest.alerting.thresholds
        daily = view.daily(["blood_glucose", "fasting_insulin"], days=30)
        g = daily.dropna(subset=["blood_glucose"])
        if len(g) < 3:
            return Assessment.unavailable(view.astronaut_id, self.manifest, "insufficient_data",
                                          f"Needs at least 3 days of glucose readings (have {len(g)}).")
        out: dict = {}
        contrib: list[Contribution] = []
        notes: list[str] = []
        sev = "none"
        last14 = g.tail(14)["blood_glucose"]
        out["fasting_mean_14d"] = round(float(last14.mean()), 1)
        out["fasting_sd_14d"] = round(float(last14.std()), 1) if len(last14) > 2 else None
        out["days_outside_reference_14d"] = int(((last14 < REF[0]) | (last14 > REF[1])).sum())
        contrib.append(Contribution(metric="blood_glucose", value=float(g["blood_glucose"].iloc[-1]), unit="mg/dL",
                                    baseline=out["fasting_mean_14d"], note=f"reference {REF[0]:.0f}-{REF[1]:.0f} mg/dL"))
        # HOMA-IR only from a real insulin measurement close in time to a glucose reading
        ins = daily.dropna(subset=["fasting_insulin"])
        if len(ins):
            d_ins = ins["date"].iloc[-1]
            near = g[(g["date"] - d_ins).abs() <= pd.Timedelta(days=2)]
            if len(near):
                h = homa_ir(float(near["blood_glucose"].iloc[-1]), float(ins["fasting_insulin"].iloc[-1]))
                out["homa_ir"] = h
                if h is not None:
                    contrib.append(Contribution(metric="fasting_insulin", value=float(ins["fasting_insulin"].iloc[-1]),
                                                unit="µIU/mL", note=f"HOMA-IR {h}"))
                    if h >= th.get("homa_ir_info", 2.5):
                        sev = "info"
                        notes.append(f"HOMA-IR {h} is above {th.get('homa_ir_info', 2.5)}, a common (population-dependent) "
                                     "insulin-resistance cut-off.")
        # CGM-style analysis only when dense data exists
        s = view.series("blood_glucose", days=14)
        if len(s):
            s = s.copy()
            s["day"] = pd.to_datetime(s["timestamp"]).dt.date
            dense_days = (s.groupby("day").size() >= 48).sum()
            if dense_days >= 3:
                cg = s.set_index(pd.to_datetime(s["timestamp"]))["value"].resample("15min").mean().dropna()
                m = cgm_metrics(cg)
                night = cg[cg.index.hour < 6]
                m["night_mean_mg_dl"] = round(float(night.mean()), 1) if len(night) else None
                out["cgm"] = m
                if m.get("valid") and m.get("night_mean_mg_dl") is not None:
                    x = pd.DataFrame([[m.get(f) for f in self.bundle["ir_features"]]], columns=self.bundle["ir_features"])
                    p = float(self.bundle["ir_model"].predict_proba(x)[0, 1])
                    out["p_insulin_resistance_pattern"] = round(p, 3)
                    if p >= th.get("ir_probability_info", 0.8):
                        sev = "info"
                        notes.append(f"CGM pattern resembles insulin resistance (research model, p = {p:.2f}).")
        trend = None
        if len(g) >= 10:
            y = g.tail(14)["blood_glucose"].to_numpy(float)
            trend = round(float(np.polyfit(np.arange(len(y)), y, 1)[0] * 7), 1)
            out["trend_mg_dl_per_week"] = trend
        rep = self.report() or {}
        ir_auc = (rep.get("insulin_resistance_from_cgm") or {}).get("auc")
        return Assessment(
            astronaut_id=view.astronaut_id, model_id=self.manifest.id, model_version=self.manifest.version, status="ok",
            category=self.manifest.category, severity=sev, score=out.get("homa_ir", out.get("p_insulin_resistance_pattern")),
            score_label=("HOMA-IR" if "homa_ir" in out else "insulin-resistance pattern probability" if "p_insulin_resistance_pattern" in out else ""),
            scale="HOMA-IR (unitless) or probability",
            calibration=(f"CGM insulin-resistance flag: leave-one-subject-out AUC {ir_auc} on CGMacros (n=45)." if ir_auc else ""),
            data_as_of=str(g["date"].iloc[-1].date()),
            explanation=(f"Fasting glucose averaged {out['fasting_mean_14d']} mg/dL over the last {len(last14)} readings"
                         + (f", trending {trend:+} mg/dL per week" if trend is not None else "")
                         + f"; {out['days_outside_reference_14d']} outside {REF[0]:.0f}-{REF[1]:.0f} mg/dL. " + " ".join(notes)).strip(),
            contributing=contrib,
            recommendation=("Spaceflight can raise insulin resistance even when glucose looks normal (NASA cardiovascular evidence "
                            "report). Discuss a fasting insulin / HOMA-IR check with the flight surgeon." if sev != "none" else ""),
            limitations=["Glucose patterns are not a validated substitute for laboratory insulin-resistance testing.",
                         "CGMacros: 45 Earth-based adults; not validated on astronauts.",
                         "HOMA-IR cut-offs differ between populations."],
            evidence_level=self.manifest.evidence_level, outputs=out)
