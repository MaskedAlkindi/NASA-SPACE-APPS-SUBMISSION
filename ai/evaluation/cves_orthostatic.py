"""Model E - orthostatic response features on PhysioNet CVES sit-to-stand recordings (ODC-By).

Checks:
  1. Signal processing: our sit->stand SBP/DBP change vs the study's own published values
     (subjects.csv "SBP change sit-2-stand", "DBP change sit-2-stand").
  2. Descriptive: how often consensus OH / HR-rise criteria are met; association with self-reported
     orthostatic symptoms (dizziness / OH symptoms) - AUC of SBP drop, exploratory.
Stand time = second marker pulse in the recording (protocol: ~5 min sitting, ~5 min standing).

    python -m ai.evaluation.cves_orthostatic
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.metrics import roc_auc_score

from ai.datasets.common import dataset_dir, provenance
from ai.preprocessing.orthostatic import beats_from_abp, response

D = dataset_dir("cves")
REPORT = Path(__file__).resolve().parents[1] / "models" / "orthostatic" / "report.json"


def _col(df: pd.DataFrame, pattern: str) -> str | None:
    return next((c for c in df.columns if re.search(pattern, c, re.I)), None)


def stand_time(marker: np.ndarray, fs: float) -> float | None:
    on = np.where(np.diff((np.asarray(marker) > 0.5).astype(int)) == 1)[0] / fs
    pulses = [on[0]] if len(on) else []
    for x in on[1:]:
        if x - pulses[-1] > 30:
            pulses.append(x)
    return float(pulses[1]) if len(pulses) >= 2 else None


def run() -> dict:
    import wfdb
    if provenance("cves") is None:
        raise FileNotFoundError("python -m ai.datasets.others download cves")
    subj = pd.read_csv(D / "subjects.csv", low_memory=False)
    c_sbp, c_dbp = _col(subj, r"^SBP change sit-2-stand"), _col(subj, r"^DBP change sit-2-stand")
    c_dizzy, c_oh = _col(subj, r"^Dizziness AUTONOMIC"), _col(subj, r"^OH AUTONOMIC")
    rows = []
    for hea in sorted(D.glob("*-sit-stand.hea")):
        rec = hea.with_suffix("")
        sid = rec.name.split("-")[0].upper()
        try:
            r = wfdb.rdrecord(str(rec))
        except Exception as e:   # noqa: BLE001
            rows.append({"subject": sid, "error": str(e)})
            continue
        names = r.sig_name
        if "abp" not in names or "marker" not in names:
            rows.append({"subject": sid, "error": "missing abp/marker"})
            continue
        st = stand_time(r.p_signal[:, names.index("marker")], r.fs)
        if st is None:
            rows.append({"subject": sid, "error": "stand marker not found"})
            continue
        beats = beats_from_abp(r.p_signal[:, names.index("abp")], r.fs)
        res = response(beats, st)
        # same windows as the study (whole sitting vs whole standing segment) for the verification check
        t = beats["t"]
        sit_m, stand_m = (t >= 15) & (t < st - 5), (t > st + 5) & (t <= st + 300)
        seg = {f"seg_delta_{k}": round(float(np.median(beats[k][stand_m]) - np.median(beats[k][sit_m])), 1)
               for k in ("sbp", "dbp")} if sit_m.sum() > 30 and stand_m.sum() > 30 else {}
        rows.append({"subject": sid, "stand_s": round(st, 1), **seg, **({k: v for k, v in res.items() if k != "baseline"}),
                     **({f"base_{k}": v for k, v in res.get("baseline", {}).items()})})
    df = pd.DataFrame(rows)
    subj["subject"] = subj["subject_number"].str.upper()
    m = df.merge(subj[["subject", c_sbp, c_dbp, c_dizzy, c_oh, "group"]], on="subject", how="left")
    v = m[m.get("valid", False) == True]  # noqa: E712
    agree = {}
    # The published column is SIT minus STAND (r=0.993 with the study's own segment means); ours is STAND minus SIT.
    for ours, theirs in (("seg_delta_sbp", c_sbp), ("seg_delta_dbp", c_dbp), ("delta_sbp", c_sbp), ("delta_dbp", c_dbp)):
        if ours not in v:
            continue
        p = v[[ours, theirs]].apply(pd.to_numeric, errors="coerce").dropna()
        p[theirs] = -p[theirs]
        if len(p) >= 5:
            agree[ours] = {"n": int(len(p)), "pearson_r": round(float(pearsonr(p[ours], p[theirs])[0]), 3),
                           "mean_abs_diff_mmHg": round(float((p[ours] - p[theirs]).abs().mean()), 1),
                           "window": "whole 5-min segments (study's windows)" if ours.startswith("seg") else "first 3 min after standing (consensus OH window)"}
    sym = v.copy()
    sym["symptom"] = sym[[c_dizzy, c_oh]].apply(lambda r: any(str(x).strip().upper() == "YES" for x in r), axis=1)
    assoc = None
    if sym["symptom"].nunique() == 2:
        assoc = {"n": int(len(sym)), "with_symptoms": int(sym["symptom"].sum()),
                 "auc_sbp_drop": round(float(roc_auc_score(sym["symptom"], -sym["delta_sbp"])), 3),
                 "auc_hr_rise": round(float(roc_auc_score(sym["symptom"], sym["hr_peak_rise"])), 3)}
    report = {
        "model_id": "orthostatic", "dataset": "CVES v1.0.0 sit-to-stand", "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_type": "signal-processing verification + descriptive statistics (research prototype)",
        "recordings": int(len(df)), "valid": int(len(v)),
        "failed": df[df.get("error").notna()]["error"].value_counts().to_dict() if "error" in df else {},
        "agreement_with_published_sit2stand_change": agree,
        "criteria_met": {"oh_pct": round(float(v["oh_criterion"].mean() * 100), 1), "hr_rise_ge30_pct": round(float(v["hr_rise_criterion"].mean() * 100), 1)},
        "median_changes": {k: round(float(v[k].median()), 1) for k in ("delta_sbp", "delta_dbp", "delta_hr", "hr_peak_rise")},
        "association_with_self_reported_symptoms": assoc,
        "population": subj["group"].value_counts().to_dict(),
        "limitations": ["Older adults with/without stroke, hypertension or diabetes - very different from astronauts.",
                        "Sit-to-stand is a milder challenge than tilt or landing; symptoms are self-reported history, not during the test.",
                        "Earth-based; does not establish astronaut return-to-gravity prediction accuracy."],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=1, default=str))
