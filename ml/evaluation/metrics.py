"""Evaluation helpers (simulation metrics only)."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import (mean_absolute_error, mean_squared_error, precision_score, r2_score,
                             recall_score, roc_auc_score)


def classification_report(y_true, scores, threshold) -> dict:
    y_true = np.asarray(y_true)
    scores = np.asarray(scores)
    pred = scores >= threshold
    return {
        "roc_auc": round(float(roc_auc_score(y_true, scores)), 4) if len(set(y_true)) > 1 else None,
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "false_positive_rate": round(float(pred[y_true == 0].mean()), 4) if (y_true == 0).any() else None,
        "n": int(len(y_true)), "n_positive": int(y_true.sum()),
    }


def regression_report(y_true, y_pred) -> dict:
    return {
        "mae": round(float(mean_absolute_error(y_true, y_pred)), 4),
        "rmse": round(float(np.sqrt(mean_squared_error(y_true, y_pred))), 4),
        "r2": round(float(r2_score(y_true, y_pred)), 4),
        "n": int(len(y_true)),
    }
