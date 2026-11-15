"""Daily feature builder shared by training (PMData) and inference (the app).

Input: one person's daily frame with canonical metric columns (any subset):
  resting_heart_rate [bpm], sleep_duration [h], sleep_efficiency [%], sleep_midpoint [h],
  steps [count], exercise_minutes [min]
Every feature uses only the same day and earlier days (causal), so the same code
is valid at inference time.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ai.preprocessing.signals import causal_baseline

BASE_METRICS = ["resting_heart_rate", "sleep_duration", "sleep_efficiency", "sleep_midpoint", "steps", "exercise_minutes"]

FEATURES = [
    "rhr_z", "rhr_delta", "sleep_h", "sleep_z", "sleep_debt_3d", "sleep_eff", "midpoint_sd_3d",
    "steps_z", "exercise_prev", "exercise_7d", "exercise_z",
]


def build(df: pd.DataFrame) -> pd.DataFrame:
    d = df.sort_values("date").reset_index(drop=True).copy()
    for m in BASE_METRICS:
        if m not in d.columns:
            d[m] = np.nan
    d = d.set_index(pd.to_datetime(d["date"])).asfreq("D")      # keep calendar gaps explicit
    out = pd.DataFrame(index=d.index)
    b = causal_baseline(d["resting_heart_rate"], window=28, gap=1, min_periods=7)
    out["rhr_z"] = b["z"].clip(-6, 6)
    out["rhr_delta"] = d["resting_heart_rate"] - b["base_median"]
    out["sleep_h"] = d["sleep_duration"]
    sb = causal_baseline(d["sleep_duration"], window=28, gap=1, min_periods=7)
    out["sleep_z"] = sb["z"].clip(-6, 6)
    debt = (sb["base_median"] - d["sleep_duration"]).clip(lower=0)
    out["sleep_debt_3d"] = debt.rolling(3, min_periods=2).sum()
    out["sleep_eff"] = d["sleep_efficiency"]
    out["midpoint_sd_3d"] = d["sleep_midpoint"].rolling(3, min_periods=2).std()
    stb = causal_baseline(d["steps"], window=28, gap=1, min_periods=7)
    out["steps_z"] = stb["z"].clip(-6, 6)
    out["exercise_prev"] = d["exercise_minutes"].shift(1)
    out["exercise_7d"] = d["exercise_minutes"].rolling(7, min_periods=4).sum()
    eb = causal_baseline(d["exercise_minutes"], window=28, gap=1, min_periods=7)
    out["exercise_z"] = eb["z"].clip(-6, 6)
    out = out.reset_index().rename(columns={"index": "date"})
    out["date"] = out["date"].dt.normalize()
    return out
