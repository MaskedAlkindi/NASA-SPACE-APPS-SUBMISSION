"""Model C - glucose and metabolic monitoring on CGMacros (PhysioNet, CC BY-NC-SA 4.0).

1. HOMA-IR per participant from fasting lab glucose [mg/dL] and insulin [uU/mL] (Matthews 1985: G x I / 405).
   Glycaemic group from HbA1c (%) using ADA cut-offs: <5.7 normal, 5.7-6.4 prediabetes, >=6.5 diabetes.
   (The data dictionary says HbA1c is in mmol/mol, but values 4.6-8.5 are clearly %, so % is used.)
2. CGM pattern -> insulin-resistance flag (HOMA-IR >= 2.5): can ~10 days of CGM summary metrics flag likely
   insulin resistance? Leave-one-subject-out, logistic regression, AUC with bootstrap 95% CI.
   This is a screening-style research signal, NOT a substitute for laboratory testing.
3. Post-meal glucose rise: peak glucose 0-120 min after a logged meal minus the pre-meal level, predicted from
   meal macros + pre-meal glucose + the person's CGM profile. Leave-one-subject-out vs a carbs-only baseline.

    python -m ai.training.train_glucose_cgmacros
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
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import mean_absolute_error, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ai.datasets.common import dataset_dir, provenance
from ai.preprocessing.signals import cgm_metrics, homa_ir

HERE = Path(__file__).resolve().parents[1] / "models" / "glucose_metabolic"
RAW = dataset_dir("cgmacros") / "raw" / "CGMacros"
CGM_FEATURES = ["mean_mg_dl", "sd_mg_dl", "cv_pct", "tir_70_180_pct", "tar_180_pct", "night_mean_mg_dl"]
IR_CUTOFF = 2.5


def participants() -> pd.DataFrame:
    bio = pd.read_csv(RAW / "bio.csv")
    bio.columns = [c.strip() for c in bio.columns]
    rows = []
    for _, b in bio.iterrows():
        sid = int(b["subject"])
        f = RAW / f"CGMacros-{sid:03d}" / f"CGMacros-{sid:03d}.csv"
        if not f.exists():
            continue
        df = pd.read_csv(f, parse_dates=["Timestamp"])
        col = "Libre GL" if df["Libre GL"].notna().mean() >= df["Dexcom GL"].notna().mean() else "Dexcom GL"
        g = df.set_index("Timestamp")[col].resample("15min").mean().dropna()   # CGM-like 15-min sampling
        m = cgm_metrics(g)
        night = g[(g.index.hour >= 0) & (g.index.hour < 6)]
        a1c = pd.to_numeric(b["A1c PDL (Lab)"], errors="coerce")
        glu = pd.to_numeric(b["Fasting GLU - PDL (Lab)"], errors="coerce")
        ins = pd.to_numeric(b["Insulin"], errors="coerce")
        rows.append({"subject": sid, "cgm_device": col, **{k: m.get(k) for k in CGM_FEATURES if k in m},
                     "night_mean_mg_dl": float(night.mean()) if len(night) else np.nan, "cgm_days": round(len(g) / 96, 1),
                     "a1c_pct": a1c, "fasting_glucose": glu, "fasting_insulin": ins,
                     "homa_ir": homa_ir(float(glu), float(ins)) if pd.notna(glu) and pd.notna(ins) else None,
                     "group": "diabetes" if a1c >= 6.5 else "prediabetes" if a1c >= 5.7 else "normal" if pd.notna(a1c) else None,
                     "bmi": pd.to_numeric(b["BMI"], errors="coerce")})
    return pd.DataFrame(rows)


def meals(ppl: pd.DataFrame) -> pd.DataFrame:
    out = []
    for sid in ppl["subject"]:
        f = RAW / f"CGMacros-{sid:03d}" / f"CGMacros-{sid:03d}.csv"
        df = pd.read_csv(f, parse_dates=["Timestamp"]).set_index("Timestamp")
        col = ppl.loc[ppl["subject"] == sid, "cgm_device"].iloc[0]
        g = df[col]
        for t, r in df[df["Meal Type"].notna() & df["Carbs"].notna()].iterrows():
            pre = g[t - pd.Timedelta(minutes=30): t].dropna()
            post = g[t: t + pd.Timedelta(minutes=120)].dropna()
            if len(pre) < 5 or len(post) < 60:
                continue
            out.append({"subject": sid, "time": t, "hour": t.hour + t.minute / 60, "meal_type": str(r["Meal Type"]).lower(),
                        "calories": r["Calories"], "carbs": r["Carbs"], "protein": r["Protein"], "fat": r["Fat"],
                        "fiber": r["Fiber"], "pre_glucose": float(pre.iloc[-1]),
                        "rise": float(post.max() - pre.iloc[-1])})
    return pd.DataFrame(out)


def boot_auc(y, p, n=2000, seed=1):
    rng = np.random.default_rng(seed)
    y, p = np.asarray(y), np.asarray(p)
    vals = []
    for _ in range(n):
        i = rng.integers(0, len(y), len(y))
        if len(set(y[i])) == 2:
            vals.append(roc_auc_score(y[i], p[i]))
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)]


def run() -> dict:
    if provenance("cgmacros") is None:
        raise FileNotFoundError("python -m ai.datasets.others download cgmacros")
    ppl = participants()
    # ---- insulin resistance from CGM profile (LOSO)
    d = ppl.dropna(subset=["homa_ir"] + CGM_FEATURES).copy()
    d["ir"] = (d["homa_ir"] >= IR_CUTOFF).astype(int)
    probs = np.full(len(d), np.nan)
    for i in range(len(d)):
        tr = np.ones(len(d), bool)
        tr[i] = False
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000))
        m.fit(d.loc[tr, CGM_FEATURES], d.loc[tr, "ir"])
        probs[i] = m.predict_proba(d.iloc[[i]][CGM_FEATURES])[0, 1]
    auc = roc_auc_score(d["ir"], probs)
    ir_model = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, class_weight="balanced", max_iter=2000)).fit(d[CGM_FEATURES], d["ir"])
    corr = {f: round(float(spearmanr(d[f], d["homa_ir"])[0]), 3) for f in CGM_FEATURES}
    # ---- post-meal rise (LOSO by subject)
    ml = meals(ppl).merge(ppl[["subject", "mean_mg_dl", "cv_pct"]], on="subject")
    feats = ["carbs", "protein", "fat", "fiber", "pre_glucose", "hour", "mean_mg_dl", "cv_pct"]
    pred_full, pred_carb = np.full(len(ml), np.nan), np.full(len(ml), np.nan)
    for sid in ml["subject"].unique():
        te = ml["subject"] == sid
        gb = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=8, l2_regularization=1.0, random_state=3)
        gb.fit(ml.loc[~te, feats], ml.loc[~te, "rise"])
        pred_full[te.to_numpy()] = gb.predict(ml.loc[te, feats])
        lr = LinearRegression().fit(ml.loc[~te, ["carbs"]].fillna(0), ml.loc[~te, "rise"])
        pred_carb[te.to_numpy()] = lr.predict(ml.loc[te, ["carbs"]].fillna(0))
    meal_model = HistGradientBoostingRegressor(max_iter=200, learning_rate=0.05, max_leaf_nodes=8, l2_regularization=1.0,
                                               random_state=3).fit(ml[feats], ml["rise"])
    report = {
        "model_id": "glucose_metabolic", "dataset": "CGMacros v1.0.0", "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sklearn_version": sklearn.__version__,
        "participants": int(len(ppl)), "groups_from_hba1c": ppl["group"].value_counts().to_dict(),
        "homa_ir": {"formula": "fasting glucose [mg/dL] x fasting insulin [uU/mL] / 405 (Matthews 1985)",
                    "n": int(ppl["homa_ir"].notna().sum()), "median": round(float(ppl["homa_ir"].median()), 2),
                    "iqr": [round(float(ppl["homa_ir"].quantile(q)), 2) for q in (0.25, 0.75)],
                    "by_group_median": ppl.groupby("group")["homa_ir"].median().round(2).to_dict(),
                    "cutoff_used": IR_CUTOFF, "cutoff_note": "HOMA-IR cut-offs vary by population (commonly 2.0-2.9); 2.5 used here for illustration."},
        "insulin_resistance_from_cgm": {"n": int(len(d)), "positives": int(d["ir"].sum()), "evaluation": "leave-one-subject-out",
                                        "auc": round(float(auc), 3), "auc_95ci_bootstrap": boot_auc(d["ir"], probs),
                                        "spearman_cgm_feature_vs_homa_ir": corr, "features": CGM_FEATURES},
        "postprandial_rise": {"meals": int(len(ml)), "subjects": int(ml["subject"].nunique()), "evaluation": "leave-one-subject-out",
                              "mae_mg_dl_model": round(float(mean_absolute_error(ml["rise"], pred_full)), 1),
                              "mae_mg_dl_carbs_only_linear": round(float(mean_absolute_error(ml["rise"], pred_carb)), 1),
                              "mae_mg_dl_predict_mean": round(float(np.mean(np.abs(ml["rise"] - ml["rise"].mean()))), 1),
                              "spearman_pred_vs_actual": round(float(spearmanr(pred_full, ml["rise"])[0]), 3),
                              "features": feats},
        "limitations": ["45 adults, ~10 days each; Earth-based, not astronauts.",
                        "CGM-based insulin-resistance flag is a research signal, not a validated alternative to fasting insulin / HOMA-IR or clamp testing.",
                        "The app's astronauts have daily fasting glucose, not CGM or meal logs, so the CGM parts run only if CGM data is supplied."],
    }
    HERE.mkdir(parents=True, exist_ok=True)
    (HERE / "artifacts").mkdir(exist_ok=True)
    joblib.dump({"ir_model": ir_model, "ir_features": CGM_FEATURES, "ir_cutoff": IR_CUTOFF,
                 "meal_model": meal_model, "meal_features": feats}, HERE / "artifacts" / "glucose_cgmacros_v1.joblib")
    (HERE / "report.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("participants", "groups_from_hba1c", "homa_ir", "insulin_resistance_from_cgm", "postprandial_rise")}, indent=1, default=str))
