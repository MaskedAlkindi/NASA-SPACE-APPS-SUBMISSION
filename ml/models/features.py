"""Feature engineering shared by training and inference.

Input everywhere is a *daily* DataFrame for ONE astronaut with a ``date`` column
and any subset of the daily metric columns below. Missing columns / values are
allowed; downstream models report which inputs were unavailable.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ANOMALY_FEATURES = ["resting_heart_rate", "hrv_sdnn", "sleep_duration", "steps"]
FATIGUE_FEATURES = ["sleep_last", "sleep_debt_3d", "sleep_midpoint_sd_3d", "sleep_efficiency_last",
                    "exercise_prev", "workload_today", "fatigue_prev"]
SLEEP_REFERENCE_H = 7.5  # fixed reference for sleep-debt feature (documented assumption)

BASELINE_WINDOW = 21     # days used for personal baseline
BASELINE_GAP = 2         # most recent days excluded so an ongoing episode does not hide itself
MIN_BASELINE_DAYS = 7
MIN_SCALE = {"resting_heart_rate": 1.5, "hrv_sdnn": 3.0, "sleep_duration": 0.3, "steps": 400.0,
             "body_temperature": 0.15, "blood_glucose": 4.0, "reaction_time": 8.0}


def ensure_columns(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c not in df.columns:
            df[c] = np.nan
    return df


def personal_baseline(df: pd.DataFrame, idx: int, metric: str) -> dict | None:
    """Robust baseline (median / scaled MAD) from the window before row ``idx``."""
    lo = max(0, idx - BASELINE_GAP - BASELINE_WINDOW)
    hi = max(0, idx - BASELINE_GAP)
    window = df[metric].iloc[lo:hi].dropna() if metric in df.columns else pd.Series(dtype=float)
    if len(window) < MIN_BASELINE_DAYS:
        return None
    med = float(window.median())
    mad = float((window - med).abs().median()) * 1.4826
    scale = max(mad, MIN_SCALE.get(metric, 1e-6), float(window.std(ddof=0)) * 0.5)
    return {"median": med, "scale": scale, "n_days": int(len(window)),
            "p10": float(window.quantile(0.1)), "p90": float(window.quantile(0.9))}


def anomaly_matrix(df: pd.DataFrame) -> tuple[np.ndarray, list[dict]]:
    """Return per-day z-score matrix (rows with insufficient baseline are NaN rows)
    plus per-row details used for explanations."""
    df = ensure_columns(df.sort_values("date").reset_index(drop=True), ANOMALY_FEATURES)
    X = np.full((len(df), len(ANOMALY_FEATURES)), np.nan)
    details: list[dict] = []
    for i in range(len(df)):
        row_detail = {}
        for j, m in enumerate(ANOMALY_FEATURES):
            base = personal_baseline(df, i, m)
            val = df[m].iloc[i]
            if base is None or pd.isna(val):
                row_detail[m] = {"value": None if pd.isna(val) else float(val), "baseline": base, "z": None}
                continue
            z = (float(val) - base["median"]) / base["scale"]
            X[i, j] = z
            row_detail[m] = {"value": float(val), "baseline": base, "z": z}
        details.append(row_detail)
    return X, details


def fatigue_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Features for estimating the fatigue score reported on each day."""
    df = ensure_columns(df.sort_values("date").reset_index(drop=True),
                        ["sleep_duration", "sleep_midpoint", "sleep_efficiency", "exercise_minutes",
                         "workload_tlx", "fatigue_score"])
    out = pd.DataFrame({"date": df["date"]})
    out["sleep_last"] = df["sleep_duration"]
    debt = np.maximum(0.0, SLEEP_REFERENCE_H - df["sleep_duration"])
    out["sleep_debt_3d"] = debt.rolling(3, min_periods=2).sum()
    out["sleep_midpoint_sd_3d"] = df["sleep_midpoint"].rolling(3, min_periods=2).std(ddof=0)
    out["sleep_efficiency_last"] = df["sleep_efficiency"]
    out["exercise_prev"] = df["exercise_minutes"].shift(1)
    out["workload_today"] = df["workload_tlx"]
    out["fatigue_prev"] = df["fatigue_score"].shift(1)
    if "fatigue_score" in df.columns:
        out["target"] = df["fatigue_score"]
    return out
