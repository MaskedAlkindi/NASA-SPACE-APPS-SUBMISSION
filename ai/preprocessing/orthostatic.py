"""Orthostatic (sit/lie -> stand) response features from beat-to-beat blood pressure.

Consensus definitions used (Freeman et al., Clin Auton Res 2011):
  orthostatic hypotension (OH): sustained SBP fall >= 20 mmHg or DBP fall >= 10 mmHg within 3 min of standing
  excessive HR rise:            HR increase >= 30 bpm within 10 min of standing (POTS criterion, adults)
These are research features. On Earth they inform further assessment; they do not predict an astronaut's
tolerance of re-entry or landing.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks


def beats_from_abp(abp: np.ndarray, fs: float) -> dict:
    """Systolic peaks, diastolic troughs and beat-to-beat HR from an arterial pressure waveform."""
    x = np.asarray(abp, float)
    x = np.where(np.isfinite(x), x, np.nanmedian(x))
    peaks, _ = find_peaks(x, distance=int(0.33 * fs), prominence=15)
    sbp = x[peaks]
    dbp = np.array([x[a:b].min() for a, b in zip(peaks[:-1], peaks[1:])])
    t = peaks / fs
    ibi = np.diff(t)
    ok = (ibi > 0.3) & (ibi < 2.0) & (sbp[1:] > 60) & (sbp[1:] < 260) & (dbp > 25) & (dbp < 160)
    return {"t": t[1:][ok], "sbp": sbp[1:][ok], "dbp": dbp[ok], "hr": 60.0 / ibi[ok]}


def response(beats: dict, stand_t: float, baseline_s: float = 120, window_s: float = 180) -> dict:
    t = beats["t"]
    pre = (t >= stand_t - baseline_s) & (t < stand_t - 5)
    post = (t >= stand_t + 15) & (t <= stand_t + window_s)          # skip the first 15 s transient
    if pre.sum() < 30 or post.sum() < 30:
        return {"valid": False}
    b = {k: float(np.median(beats[k][pre])) for k in ("sbp", "dbp", "hr")}
    # sustained change = median of the standing window; nadir = 10th percentile (robust to artefacts)
    d = {f"delta_{k}": float(np.median(beats[k][post]) - b[k]) for k in ("sbp", "dbp", "hr")}
    nadir_sbp = float(np.percentile(beats["sbp"][post], 10) - b["sbp"])
    peak_hr = float(np.percentile(beats["hr"][(t >= stand_t) & (t <= stand_t + 600)], 90) - b["hr"])
    return {"valid": True, "baseline": {k: round(v, 1) for k, v in b.items()},
            **{k: round(v, 1) for k, v in d.items()}, "sbp_nadir_drop": round(nadir_sbp, 1), "hr_peak_rise": round(peak_hr, 1),
            "oh_criterion": bool(d["delta_sbp"] <= -20 or d["delta_dbp"] <= -10),
            "hr_rise_criterion": bool(peak_hr >= 30)}
