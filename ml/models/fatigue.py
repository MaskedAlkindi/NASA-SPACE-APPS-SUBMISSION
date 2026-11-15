"""Model 2 - Fatigue estimation (inference).

SIMULATION MODEL: trained on synthetic labels (Samn-Perelli 1-7 scale) generated
by ml/datasets/synthetic.py. It demonstrates the pipeline; its accuracy says
nothing about real astronauts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import artifacts
from .features import FATIGUE_FEATURES, fatigue_frame

LIMITATIONS = [
    "SIMULATION MODEL: trained and evaluated on synthetic labels only.",
    "Estimates a 1-7 Samn-Perelli-style fatigue score; it is not a medical assessment.",
    "Accuracy drops when sleep or workload inputs are missing.",
]

SAMN_PERELLI = {1: "fully alert", 2: "very lively", 3: "okay, somewhat fresh", 4: "a little tired",
                5: "moderately tired", 6: "extremely tired", 7: "completely exhausted"}


class FatigueModel:
    def __init__(self):
        bundle = artifacts.load_joblib(artifacts.FATIGUE_VERSION)
        self.available = bundle is not None
        if bundle:
            self.model = bundle["model"]
            self.residual_q = bundle["residual_quantiles"]   # (q10, q90) of held-out residuals
            self.metrics = bundle.get("metrics", {})
            self.importances = bundle.get("importances", {})

    def estimate_latest(self, daily: pd.DataFrame) -> dict | None:
        if not self.available:
            raise RuntimeError("fatigue model artifact missing - run ml training")
        if daily.empty:
            return None
        feats = fatigue_frame(daily)
        last = feats.iloc[[-1]]
        X = last[FATIGUE_FEATURES].astype(float)
        missing = [c for c in FATIGUE_FEATURES if pd.isna(X[c].iloc[0])]
        if len(missing) > 4:
            return {"status": "insufficient_data", "missing": missing}
        pred = float(np.clip(self.model.predict(X.to_numpy())[0], 1, 7))
        lo = float(np.clip(pred + self.residual_q[0], 1, 7))
        hi = float(np.clip(pred + self.residual_q[1], 1, 7))
        level = int(round(pred))
        return {
            "status": "estimated", "date": str(pd.Timestamp(last["date"].iloc[0]).date()),
            "fatigue_estimate": round(pred, 2), "interval_80": [round(lo, 2), round(hi, 2)],
            "scale": "Samn-Perelli 1 (fully alert) - 7 (completely exhausted)",
            "category": SAMN_PERELLI.get(level, ""),
            "inputs": {c: (None if pd.isna(X[c].iloc[0]) else round(float(X[c].iloc[0]), 2)) for c in FATIGUE_FEATURES},
            "missing": missing,
            "data_type": "simulation_model",
        }
