"""Train + evaluate Model 2 (fatigue estimation, SIMULATED labels)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

from ml.evaluation.metrics import regression_report
from ml.models import artifacts
from ml.models.features import FATIGUE_FEATURES, fatigue_frame
from ml.training.common import SEED, split_population


def build(pop: pd.DataFrame, rng: np.random.Generator, drop_rate: float = 0.08):
    frames = [fatigue_frame(g) for _, g in pop.groupby("astronaut_id")]
    df = pd.concat(frames, ignore_index=True).dropna(subset=["target"])
    X = df[FATIGUE_FEATURES].astype(float).to_numpy()
    # Simulate missing sensor data so the model learns to cope (native NaN support).
    mask = rng.random(X.shape) < drop_rate
    X[mask] = np.nan
    return X, df["target"].to_numpy(), df


def train(verbose: bool = True) -> dict:
    rng = np.random.default_rng(SEED)
    train_pop, test_pop = split_population()
    X_tr, y_tr, _ = build(train_pop, rng)
    X_te, y_te, df_te = build(test_pop, rng)
    model = HistGradientBoostingRegressor(max_iter=250, learning_rate=0.06, max_leaf_nodes=15,
                                          l2_regularization=0.5, random_state=SEED)
    model.fit(X_tr, y_tr)
    pred = np.clip(model.predict(X_te), 1, 7)
    resid = y_te - pred
    persistence = df_te["fatigue_prev"].fillna(np.nanmean(y_tr)).to_numpy()
    imp = permutation_importance(model, X_te, y_te, n_repeats=5, random_state=SEED)
    importances = {f: round(float(v), 4) for f, v in zip(FATIGUE_FEATURES, imp.importances_mean)}
    metrics = {
        "model": regression_report(y_te, pred),
        "baseline_persistence_yesterday": regression_report(y_te, persistence),
        "baseline_mean": regression_report(y_te, np.full_like(y_te, float(np.mean(y_tr)))),
        "evaluation_data": "SIMULATED held-out astronauts (grouped split, no individual overlap)",
        "label_source": "synthetic Samn-Perelli scores from documented generative model",
        "features": FATIGUE_FEATURES, "sklearn_version": sklearn.__version__,
        "permutation_importance": importances,
    }
    artifacts.save_joblib(artifacts.FATIGUE_VERSION, {
        "model": model, "residual_quantiles": (float(np.quantile(resid, 0.1)), float(np.quantile(resid, 0.9))),
        "metrics": metrics, "importances": importances, "version": artifacts.FATIGUE_VERSION})
    if verbose:
        print("[fatigue]", metrics["model"], "| persistence:", metrics["baseline_persistence_yesterday"])
    return metrics


if __name__ == "__main__":
    train()
