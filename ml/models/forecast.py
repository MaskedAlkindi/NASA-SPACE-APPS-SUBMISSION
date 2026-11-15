"""Model 3 - Short-term trend forecasting (damped Holt linear exponential smoothing).

Smoothing parameters are chosen by rolling-origin backtests in
ml/training/train_forecast.py and stored as a versioned JSON artifact. The model
is refit on each astronaut's own series at inference time (it is tiny).
Prediction intervals come from the backtest residual spread scaled by
sqrt(horizon) - an approximation, reported as such.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import artifacts

DEFAULT_PARAMS = {"alpha": 0.4, "beta": 0.1, "phi": 0.9}
MIN_POINTS = 10
LIMITATIONS = [
    "Statistical extrapolation of recent trend; cannot anticipate new events.",
    "Interval widths are approximate (backtest residuals on simulated data).",
    "Forecasts are not diagnoses.",
]


def holt_fit(y: np.ndarray, alpha: float, beta: float, phi: float):
    level, trend = y[0], (y[min(len(y) - 1, 3)] - y[0]) / max(1, min(len(y) - 1, 3))
    fitted = []
    for t in range(1, len(y)):
        pred = level + phi * trend
        fitted.append(pred)
        new_level = alpha * y[t] + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    return level, trend, np.array(fitted)


def holt_forecast(level: float, trend: float, phi: float, horizon: int) -> np.ndarray:
    out, damp = [], 0.0
    for h in range(1, horizon + 1):
        damp += phi ** h
        out.append(level + damp * trend)
    return np.array(out)


class TrendForecaster:
    def __init__(self):
        cfg = artifacts.load_json(artifacts.FORECAST_VERSION)
        self.available = cfg is not None
        self.cfg = cfg or {"metrics": {}}

    def forecast(self, daily: pd.DataFrame, metric: str, horizon: int = 7) -> dict:
        series = daily.sort_values("date")[["date", metric]].dropna() if metric in daily.columns else pd.DataFrame()
        if len(series) < MIN_POINTS:
            return {"metric": metric, "status": "insufficient_data", "points": int(len(series)),
                    "required": MIN_POINTS}
        mcfg = self.cfg.get("metrics", {}).get(metric, {})
        p = mcfg.get("params", DEFAULT_PARAMS)
        resid_sd = mcfg.get("residual_sd_h1")
        y = series[metric].to_numpy(dtype=float)[-45:]
        level, trend, fitted = holt_fit(y, p["alpha"], p["beta"], p["phi"])
        if resid_sd is None:
            resid_sd = float(np.std(y[1:] - fitted)) if len(fitted) > 2 else float(np.std(y))
        fc = holt_forecast(level, trend, p["phi"], horizon)
        last_date = pd.Timestamp(series["date"].iloc[-1])
        z80 = 1.2816
        points = []
        for h, v in enumerate(fc, start=1):
            w = z80 * resid_sd * math.sqrt(h)
            points.append({"date": str((last_date + pd.Timedelta(days=h)).date()), "value": round(float(v), 2),
                           "lower_80": round(float(v - w), 2), "upper_80": round(float(v + w), 2)})
        recent = float(np.mean(y[-7:]))
        change = float(fc[-1] - recent)
        rel = abs(change) / max(1e-6, resid_sd)
        direction = "stable" if rel < 1.0 else ("rising" if change > 0 else "falling")
        return {"metric": metric, "status": "forecast", "horizon_days": horizon, "points": points,
                "recent_mean_7d": round(recent, 2), "projected_change": round(change, 2),
                "trend_direction": direction, "params": p,
                "backtest": mcfg.get("backtest"), "history_points_used": int(len(y))}
