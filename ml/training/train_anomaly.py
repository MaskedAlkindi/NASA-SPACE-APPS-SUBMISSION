"""Train + evaluate Model 1 (personalised Isolation Forest). Reproducible (fixed seeds)."""
from __future__ import annotations

import numpy as np
import sklearn
from sklearn.ensemble import IsolationForest

from ml.evaluation.metrics import classification_report
from ml.models import artifacts
from ml.models.features import ANOMALY_FEATURES, anomaly_matrix
from ml.training.common import SEED, split_population


def build_xy(pop):
    Xs, ys = [], []
    for _, g in pop.groupby("astronaut_id"):
        X, _ = anomaly_matrix(g)
        ok = (~np.isnan(X)).sum(axis=1) >= 2
        Xs.append(np.where(np.isnan(X[ok]), 0.0, X[ok]))
        ys.append(g.sort_values("date")["label_anomaly"].to_numpy()[ok])
    return np.vstack(Xs), np.concatenate(ys)


def train(verbose: bool = True) -> dict:
    train_pop, test_pop = split_population()
    X_tr, y_tr = build_xy(train_pop)
    X_nominal = X_tr[y_tr == 0]          # unsupervised: fit on nominal days only
    model = IsolationForest(n_estimators=300, max_samples=256, contamination="auto", random_state=SEED)
    model.fit(X_nominal)
    train_scores = -model.score_samples(X_nominal)
    threshold = float(np.quantile(train_scores, 0.975))

    X_te, y_te = build_xy(test_pop)
    te_scores = -model.score_samples(X_te)
    metrics = {
        "model": classification_report(y_te, te_scores, threshold),
        "baseline_rule_abs_z_rhr_gt_2.5": classification_report(y_te, np.abs(X_te[:, 0]), 2.5),
        "threshold_definition": "97.5th percentile of anomaly score on nominal training days",
        "evaluation_data": "SIMULATED held-out astronauts with injected cardio/illness-like episodes",
        "features": ANOMALY_FEATURES, "sklearn_version": sklearn.__version__,
        "train_days_nominal": int(len(X_nominal)),
    }
    artifacts.save_joblib(artifacts.ANOMALY_VERSION, {
        "model": model, "train_scores": train_scores, "threshold": threshold,
        "metrics": metrics, "version": artifacts.ANOMALY_VERSION, "features": ANOMALY_FEATURES})
    if verbose:
        print("[anomaly]", metrics["model"], "| rule baseline:", metrics["baseline_rule_abs_z_rhr_gt_2.5"])
    return metrics


if __name__ == "__main__":
    train()
