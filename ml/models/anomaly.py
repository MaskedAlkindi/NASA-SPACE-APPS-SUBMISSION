"""Model 1 - Personalised anomaly detection (inference).

Each day's measurements are converted to robust z-scores against the
astronaut's OWN rolling baseline, then scored by an Isolation Forest trained on
baseline-normalised nominal days. Personalisation therefore comes from the
normalisation; the forest learns what "jointly unusual" deviations look like.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import artifacts
from .features import ANOMALY_FEATURES, MIN_BASELINE_DAYS, anomaly_matrix

LIMITATIONS = [
    "Trained on simulated data only - not clinically validated.",
    "Needs at least %d days of personal baseline per metric." % MIN_BASELINE_DAYS,
    "Flags statistical unusualness relative to your own history, not disease.",
    "Missing metrics are treated as 'at baseline', which lowers sensitivity.",
]

LABELS = {"resting_heart_rate": "Resting heart rate", "hrv_sdnn": "Heart-rate variability (SDNN)",
          "sleep_duration": "Sleep duration", "steps": "Steps"}


class AnomalyDetector:
    def __init__(self):
        bundle = artifacts.load_joblib(artifacts.ANOMALY_VERSION)
        self.available = bundle is not None
        if bundle:
            self.model = bundle["model"]
            self.train_scores = np.sort(bundle["train_scores"])
            self.threshold = float(bundle["threshold"])
            self.metrics = bundle.get("metrics", {})

    def _percentile(self, s: float) -> float:
        return float(np.searchsorted(self.train_scores, s) / len(self.train_scores))

    def score_days(self, daily: pd.DataFrame) -> list[dict]:
        """Score every day in a single astronaut's daily frame."""
        if not self.available:
            raise RuntimeError("anomaly model artifact missing - run ml training")
        daily = daily.sort_values("date").reset_index(drop=True)
        X, details = anomaly_matrix(daily)
        all_scores = -self.model.score_samples(np.where(np.isnan(X), 0.0, X)) if len(X) else []
        results = []
        for i in range(len(daily)):
            row = X[i]
            have = ~np.isnan(row)
            d = str(pd.Timestamp(daily["date"].iloc[i]).date())
            if have.sum() < 2:
                results.append({"date": d, "status": "insufficient_baseline", "score": None,
                                "is_anomaly": False, "missing": [m for m, h in zip(ANOMALY_FEATURES, have) if not h]})
                continue
            raw = float(all_scores[i])
            contributors = []
            for m in ANOMALY_FEATURES:
                det = details[i][m]
                if det["z"] is None:
                    continue
                contributors.append({
                    "metric": m, "label": LABELS[m], "value": round(det["value"], 2),
                    "baseline_median": round(det["baseline"]["median"], 2),
                    "baseline_range": [round(det["baseline"]["p10"], 2), round(det["baseline"]["p90"], 2)],
                    "baseline_days": det["baseline"]["n_days"],
                    "z": round(det["z"], 2),
                    "direction": "above" if det["z"] > 0 else "below",
                })
            contributors.sort(key=lambda c: abs(c["z"]), reverse=True)
            missing = [m for m, h in zip(ANOMALY_FEATURES, have) if not h]
            pct = self._percentile(raw)
            results.append({
                "date": d, "status": "scored", "score": round(raw, 4),
                "score_percentile": round(pct, 3),
                "threshold": round(self.threshold, 4),
                "is_anomaly": raw >= self.threshold,
                "contributors": contributors,
                "missing": missing,
                "reliability": "reduced" if missing else "normal",
            })
        return results

    def latest(self, daily: pd.DataFrame) -> dict | None:
        res = self.score_days(daily)
        return res[-1] if res else None
