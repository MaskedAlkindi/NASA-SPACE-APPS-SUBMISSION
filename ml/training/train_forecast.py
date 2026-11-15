"""Select + evaluate Model 3 (damped Holt) parameters by rolling-origin backtest."""
from __future__ import annotations

import itertools

import numpy as np

from ml.models import artifacts
from ml.models.forecast import holt_fit, holt_forecast
from ml.training.common import split_population

METRICS = ["resting_heart_rate", "sleep_duration", "hrv_sdnn"]
GRID = list(itertools.product([0.05, 0.1, 0.2, 0.3, 0.5], [0.01, 0.05, 0.1], [0.5, 0.7, 0.8, 0.9]))
HORIZON = 7


def backtest(series_list, alpha, beta, phi, horizon=HORIZON):
    errs, naive, mean7, h1 = [], [], [], []
    for y in series_list:
        for origin in range(20, len(y) - horizon, 5):
            hist, fut = y[:origin], y[origin:origin + horizon]
            level, trend, _ = holt_fit(hist, alpha, beta, phi)
            fc = holt_forecast(level, trend, phi, horizon)
            errs.append(np.abs(fc - fut).mean())
            h1.append(fut[0] - fc[0])
            naive.append(np.abs(hist[-1] - fut).mean())
            mean7.append(np.abs(hist[-7:].mean() - fut).mean())
    return float(np.mean(errs)), float(np.mean(naive)), float(np.mean(mean7)), float(np.std(h1))


def train(verbose: bool = True) -> dict:
    train_pop, test_pop = split_population()
    out = {"version": artifacts.FORECAST_VERSION, "horizon_days": HORIZON, "metrics": {},
           "evaluation_data": "SIMULATED held-out astronauts, rolling-origin backtest"}
    for m in METRICS:
        tr = [g.sort_values("date")[m].to_numpy(float) for _, g in train_pop.groupby("astronaut_id")]
        te = [g.sort_values("date")[m].to_numpy(float) for _, g in test_pop.groupby("astronaut_id")]
        best = min(GRID, key=lambda p: backtest(tr, *p)[0])
        mae, naive, mean7, sd = backtest(te, *best)
        out["metrics"][m] = {
            "params": {"alpha": best[0], "beta": best[1], "phi": best[2]},
            "residual_sd_h1": round(sd, 4),
            "backtest": {"mae_model": round(mae, 4), "mae_naive_last_value": round(naive, 4),
                         "mae_mean_last_7d": round(mean7, 4), "horizon_days": HORIZON},
        }
        if verbose:
            print(f"[forecast] {m}: params={best} MAE={mae:.3f} naive={naive:.3f} mean7={mean7:.3f}")
    artifacts.save_json(artifacts.FORECAST_VERSION, out)
    return out


if __name__ == "__main__":
    train()
