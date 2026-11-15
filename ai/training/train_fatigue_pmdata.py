"""Model A - fatigue / stress from wearable data, trained on PMData with real self-reports.

Label direction (verified empirically, see report): PMSys scores run 1 = worst ... 5 = best
("fatigue" 1 = very tired, 5 = very fresh; "stress" 1 = very stressed, 5 = relaxed; 3 = normal).
Targets:
  tired   = fatigue <= 2   ("more tired than normal")
  stressed = stress <= 2   ("more stressed than normal")
Feature sets:
  wearable  - only signals the app has (resting HR, sleep, steps, exercise) as personal-baseline deviations
  +report   - wearable + yesterday's self-reported score (research comparison only; scales differ from the app's)
Evaluation: leave-one-subject-out (LOSO) over 16 people; no person is in their own training set.

    python -m ai.training.train_fatigue_pmdata
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ai.datasets.common import provenance
from ai.datasets.pmdata import load_all
from ai.preprocessing.daily_features import FEATURES, build

HERE = Path(__file__).resolve().parents[1] / "models" / "fatigue_pmdata"
SEED = 7


def canonical(df: pd.DataFrame) -> pd.DataFrame:
    """PMData columns -> the app's canonical metrics (units documented in daily_features)."""
    start = df["sleep_start_h"].where(df["sleep_start_h"] < 18, df["sleep_start_h"] - 24)   # 23:00 -> -1
    return pd.DataFrame({
        "date": df["date"], "participant": df["participant"],
        "resting_heart_rate": df["resting_hr"], "sleep_duration": df["sleep_min"] / 60,
        "sleep_efficiency": df["sleep_eff"], "sleep_midpoint": start + df["sleep_min"] / 120,
        "steps": df["steps"], "exercise_minutes": df["moderately_active"] + df["very_active"],
        "fatigue": df["fatigue"], "stress": df["stress"], "readiness": df["readiness"],
    })


def dataset() -> pd.DataFrame:
    raw = canonical(load_all())
    frames = []
    for pid, g in raw.groupby("participant"):
        f = build(g.drop(columns=["participant"]))
        lab = g[["date", "fatigue", "stress", "readiness"]].copy()
        lab["date"] = pd.to_datetime(lab["date"]).dt.normalize()
        f = f.merge(lab, on="date", how="left")
        f["fatigue_prev"] = f["fatigue"].shift(1)
        f["stress_prev"] = f["stress"].shift(1)
        f["participant"] = pid
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def models():
    return {
        "logistic": make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler(),
                                  LogisticRegression(C=0.3, class_weight="balanced", max_iter=2000)),
        "gbm": HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_leaf_nodes=8,
                                              l2_regularization=1.0, class_weight="balanced", random_state=SEED),
    }


def loso(df: pd.DataFrame, feats: list[str], target: str, kind: str):
    probs = pd.Series(np.nan, index=df.index)
    for pid in df["participant"].unique():
        tr, te = df["participant"] != pid, df["participant"] == pid
        if df.loc[tr, target].nunique() < 2:
            continue
        m = models()[kind]
        m.fit(df.loc[tr, feats], df.loc[tr, target])
        probs[te] = m.predict_proba(df.loc[te, feats])[:, 1]
    return probs


def metrics(y, p, groups) -> dict:
    ok = p.notna()
    y, p, groups = y[ok], p[ok], groups[ok]
    per = []
    for g in groups.unique():
        m = groups == g
        if y[m].nunique() == 2:
            per.append(roc_auc_score(y[m], p[m]))
    return {"n_days": int(len(y)), "positives": int(y.sum()), "auc_pooled": round(float(roc_auc_score(y, p)), 3),
            "auc_within_person_median": round(float(np.median(per)), 3) if per else None,
            "balanced_accuracy@0.5": round(float(balanced_accuracy_score(y, p >= 0.5)), 3),
            "brier": round(float(brier_score_loss(y, p)), 4), "base_rate": round(float(y.mean()), 3)}


def run() -> dict:
    if provenance("pmdata") is None:
        raise FileNotFoundError("python -m ai.datasets.pmdata download")
    df = dataset()
    direction = {k: round(float(spearmanr(df[k], df["readiness"], nan_policy="omit")[0]), 3) for k in ("fatigue", "stress")}
    results, final = {}, {}
    for label, col in (("tired", "fatigue"), ("stressed", "stress")):
        d = df.dropna(subset=[col]).copy()
        d[label] = (d[col] <= 2).astype(int)
        d = d[d[FEATURES].notna().sum(axis=1) >= 4]             # need some wearable data that day
        r = {}
        for fs_name, feats in (("wearable", FEATURES), ("wearable+yesterday_report", FEATURES + [f"{col}_prev"])):
            for kind in ("logistic", "gbm"):
                p = loso(d, feats, label, kind)
                r[f"{fs_name}/{kind}"] = metrics(d[label], p, d["participant"])
        # baselines
        prev = (d[f"{col}_prev"] <= 2).astype(float).where(d[f"{col}_prev"].notna())
        r["baseline/yesterday_report"] = metrics(d[label], prev.fillna(d[label].mean()), d["participant"])
        r["baseline/constant"] = {"auc_pooled": 0.5, "base_rate": round(float(d[label].mean()), 3)}
        results[label] = r
        # deployable model = wearable-only; pick logistic unless gbm is clearly better (>0.02 AUC)
        lg, gb = r["wearable/logistic"]["auc_pooled"], r["wearable/gbm"]["auc_pooled"]
        kind = "gbm" if gb > lg + 0.02 else "logistic"
        m = models()[kind].fit(d[FEATURES], d[label])
        coef = None
        if kind == "logistic":
            lr = m.named_steps["logisticregression"]
            names = list(FEATURES) + [f"missing_{f}" for f in np.array(FEATURES)[m.named_steps["simpleimputer"].indicator_.features_]]
            coef = {n: round(float(c), 3) for n, c in zip(names, lr.coef_[0])}
        final[label] = {"model": m, "kind": kind, "features": FEATURES, "coefficients": coef,
                        "loso": r[f"wearable/{kind}"], "base_rate": float(d[label].mean())}
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "artifacts").mkdir(exist_ok=True)
    joblib.dump({k: {kk: vv for kk, vv in v.items()} for k, v in final.items()}, HERE / "artifacts" / "fatigue_pmdata_v1.joblib")
    report = {
        "model_id": "fatigue_pmdata", "dataset": "PMData", "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__, "subjects": int(df["participant"].nunique()),
        "label_direction_check_spearman_vs_readiness": direction,
        "label_definitions": {"tired": "PMSys fatigue <= 2 (1 = very tired ... 5 = very fresh; 3 = normal)",
                              "stressed": "PMSys stress <= 2 (1 = very stressed ... 5 = relaxed; 3 = normal)"},
        "evaluation": "leave-one-subject-out over all participants; pooled and within-person AUC",
        "results": results,
        "deployed": {k: {"kind": v["kind"], "loso": v["loso"], "coefficients": v["coefficients"]} for k, v in final.items()},
        "provenance_sha256": {f["path"]: f["sha256"] for f in provenance("pmdata")["files"] if f["path"].endswith("wellness.csv")},
        "limitations": ["16 healthy adults (Norway), Fitbit Versa 2: small, Earth-based, not astronauts.",
                        "Self-reported labels; 'tired' means more tired than that person's normal.",
                        "Fitbit active minutes stand in for 'exercise minutes'; device differences are not modelled."],
    }
    (HERE / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


if __name__ == "__main__":
    rep = run()
    print(json.dumps({"direction": rep["label_direction_check_spearman_vs_readiness"], "results": rep["results"],
                      "deployed": {k: (v["kind"], v["loso"]["auc_pooled"]) for k, v in rep["deployed"].items()}}, indent=1))
