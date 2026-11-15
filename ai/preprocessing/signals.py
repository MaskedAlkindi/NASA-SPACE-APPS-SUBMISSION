"""Signal processing shared by models, training and evaluation.

HRV (time domain, Task Force of the ESC/NASPE 1996 definitions):
    SDNN  = standard deviation of NN intervals (ms)
    RMSSD = root mean square of successive NN differences (ms)
    pNN50 = % of successive NN differences > 50 ms
Artefact handling: intervals outside 0.3-2.0 s are dropped, and intervals differing
from the previous accepted one by more than 20 % are treated as ectopic/artefact.

Glucose (CGM consensus metrics, Battelino et al., Diabetes Care 2019):
    mean, SD, coefficient of variation (CV = SD/mean), time in range 70-180 mg/dL,
    time above 180, time below 70.
HOMA-IR (Matthews et al., Diabetologia 1985):
    HOMA-IR = fasting glucose [mg/dL] x fasting insulin [uIU/mL] / 405
    (equivalently glucose [mmol/L] x insulin / 22.5).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


# ------------------------------------------------------------------ HRV
def clean_rr(rr_s: np.ndarray, lo: float = 0.3, hi: float = 2.0, max_rel_jump: float = 0.2) -> np.ndarray:
    rr = np.asarray(rr_s, dtype=float)
    rr = rr[(rr >= lo) & (rr <= hi)]
    if rr.size < 2:
        return rr
    keep = [rr[0]]
    for x in rr[1:]:
        if abs(x - keep[-1]) <= max_rel_jump * keep[-1]:
            keep.append(x)
    return np.array(keep)


def hrv_time_domain(rr_s: np.ndarray, clean: bool = True) -> dict:
    raw_n = int(np.size(rr_s))
    rr = clean_rr(rr_s) if clean else np.asarray(rr_s, dtype=float)
    if rr.size < 10:
        return {"n": int(rr.size), "raw_n": raw_n, "valid": False}
    ms = rr * 1000.0
    d = np.diff(ms)
    return {"n": int(rr.size), "raw_n": raw_n, "valid": True, "kept_pct": round(100 * rr.size / max(raw_n, 1), 1),
            "mean_hr_bpm": round(60.0 / rr.mean(), 2), "sdnn_ms": round(float(ms.std(ddof=1)), 2),
            "rmssd_ms": round(float(np.sqrt(np.mean(d ** 2))), 2), "pnn50_pct": round(float(np.mean(np.abs(d) > 50) * 100), 2)}


# ------------------------------------------------------------------ baselines
def causal_baseline(s: pd.Series, window: int = 28, gap: int = 1, min_periods: int = 7,
                    min_scale: float | None = None) -> pd.DataFrame:
    """Personal baseline using only data strictly before each day (no look-ahead).

    Returns columns: base_median, base_scale (robust spread), z.
    The spread has a floor (min_scale, default 1% of the baseline level) so a perfectly
    flat history still yields a finite z-score instead of NaN.
    """
    past = s.shift(gap)
    med = past.rolling(window, min_periods=min_periods).median()
    mad = (past - med).abs().rolling(window, min_periods=min_periods).median() * 1.4826
    sd = past.rolling(window, min_periods=min_periods).std()
    floor = (med.abs() * 0.01) if min_scale is None else pd.Series(min_scale, index=s.index)
    scale = np.maximum(np.maximum(mad.fillna(0), sd.fillna(0) * 0.5), floor.fillna(0))
    scale = scale.where((scale > 0) & med.notna())
    return pd.DataFrame({"base_median": med, "base_scale": scale, "z": (s - med) / scale})


# ------------------------------------------------------------------ glucose
def cgm_metrics(glucose_mg_dl: pd.Series) -> dict:
    g = pd.to_numeric(glucose_mg_dl, errors="coerce").dropna()
    g = g[(g >= 20) & (g <= 600)]
    if len(g) < 30:
        return {"n": int(len(g)), "valid": False}
    mean, sd = float(g.mean()), float(g.std())
    return {"n": int(len(g)), "valid": True, "mean_mg_dl": round(mean, 1), "sd_mg_dl": round(sd, 1),
            "cv_pct": round(100 * sd / mean, 1), "tir_70_180_pct": round(float(((g >= 70) & (g <= 180)).mean() * 100), 1),
            "tar_180_pct": round(float((g > 180).mean() * 100), 1), "tbr_70_pct": round(float((g < 70).mean() * 100), 1)}


def homa_ir(fasting_glucose_mg_dl: float | None, fasting_insulin_uiu_ml: float | None) -> float | None:
    """HOMA-IR (Matthews 1985). Returns None unless both values are present and plausible."""
    if fasting_glucose_mg_dl is None or fasting_insulin_uiu_ml is None:
        return None
    if not (40 <= fasting_glucose_mg_dl <= 400) or not (0.5 <= fasting_insulin_uiu_ml <= 300):
        return None
    return round(fasting_glucose_mg_dl * fasting_insulin_uiu_ml / 405.0, 2)
