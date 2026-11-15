"""Model D - verify HRV / sleep / baseline processing on MMASH (PhysioNet, ODbL).

MMASH is too small (22 people, ~24 h each) to train a model. It is used to check that
the tool's signal processing matches independent references:

  1. HR from our RR processing vs the HR column recorded by the ActiGraph (per minute).
  2. Sleep efficiency recomputed from TST / time-in-bed vs the efficiency MMASH reports.
  3. Night-time HRV (RMSSD) per person, and exploratory Spearman correlations with
     the questionnaires (PSQI, Daily Stress Inventory) - descriptive only.

    python -m ai.evaluation.mmash_verification
"""
from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from ai.datasets.common import dataset_dir, provenance
from ai.preprocessing.signals import hrv_time_domain

OUT = Path(__file__).resolve().parents[1] / "models" / "sleep_hrv" / "report.json"


def _zip() -> zipfile.ZipFile:
    base = dataset_dir("mmash") / "raw" / "multilevel-monitoring-of-activity-and-sleep-in-healthy-people-1.0.0"
    z = base / "MMASH.zip"
    sums = (base / "SHA256SUMS.txt").read_text().split()
    expected = sums[sums.index("MMASH.zip") - 1]
    got = hashlib.sha256(z.read_bytes()).hexdigest()
    if got != expected:
        raise RuntimeError(f"MMASH.zip checksum mismatch: {got} != {expected}")
    return zipfile.ZipFile(z)


def _read(z, user, name):
    p = f"DataPaper/{user}/{name}"
    return pd.read_csv(io.BytesIO(z.read(p))) if p in z.namelist() else None


def _clock(day, t):
    parts = [int(float(x)) for x in str(t).split(":")[:3]] + [0, 0]
    h, m, s = parts[:3]
    return (int(day) - 1) * 86400 + h * 3600 + m * 60 + s


def run() -> dict:
    if provenance("mmash") is None:
        raise FileNotFoundError("python -m ai.datasets.others download mmash")
    z = _zip()
    users = sorted({n.split("/")[1] for n in z.namelist() if n.startswith("DataPaper/user_")})
    hr_rows, sleep_rows, people = [], [], []
    for u in users:
        rr, act, sl, q = (_read(z, u, f) for f in ("RR.csv", "Actigraph.csv", "sleep.csv", "questionnaire.csv"))
        if rr is None or act is None:
            continue
        rr = rr.dropna(subset=["ibi_s"])
        rr["sec"] = [_clock(d, t) for d, t in zip(rr["day"], rr["time"])]
        act["sec"] = [_clock(d, t) for d, t in zip(act["day"], act["time"])]
        # 1. per-minute HR from RR vs ActiGraph HR
        rr["minute"] = rr["sec"] // 60
        act["minute"] = act["sec"] // 60
        ours = rr.groupby("minute")["ibi_s"].apply(lambda x: hrv_time_domain(x.to_numpy()).get("mean_hr_bpm"))
        ref = act[act["HR"] > 0].groupby("minute")["HR"].mean()
        j = pd.concat([ours.rename("ours"), ref.rename("ref")], axis=1).dropna()
        if len(j):
            hr_rows.append({"user": u, "minutes": int(len(j)), "mae_bpm": float((j["ours"] - j["ref"]).abs().mean()),
                            "bias_bpm": float((j["ours"] - j["ref"]).mean()), "r": float(j.corr().iloc[0, 1])})
        # 2. sleep efficiency + night HRV
        night = None
        if sl is not None and len(sl):
            s0 = sl.iloc[0]
            tib = float(s0["Total Minutes in Bed"])
            tst = float(s0["Total Sleep Time (TST)"])
            if tib > 0:
                sleep_rows.append({"user": u, "reported_eff": float(s0["Efficiency"]), "recomputed_eff": 100 * tst / tib,
                                   "tst_h": tst / 60})
            onset = _clock(s0["Onset Date"], s0["Onset Time"])
            wake = onset + tst * 60 + float(s0.get("Wake After Sleep Onset (WASO)", 0)) * 60
            night = rr[(rr["sec"] >= onset) & (rr["sec"] <= wake)]["ibi_s"].to_numpy()
        hrv_night = hrv_time_domain(night) if night is not None and len(night) else {"valid": False}
        rec = {"user": u, "night_rmssd_ms": hrv_night.get("rmssd_ms"), "night_sdnn_ms": hrv_night.get("sdnn_ms"),
               "night_hr_bpm": hrv_night.get("mean_hr_bpm"), "kept_pct": hrv_night.get("kept_pct")}
        if q is not None and len(q):
            q0 = q.iloc[0]
            rec.update({k: float(q0[k]) for k in ("pittsburgh", "Daily_stress", "STAI2", "MEQ") if k in q.columns and pd.notna(q0[k])})
        people.append(rec)

    hr = pd.DataFrame(hr_rows)
    sl = pd.DataFrame(sleep_rows)
    pp = pd.DataFrame(people)
    explore = {}
    for k in ("pittsburgh", "Daily_stress", "STAI2"):
        d = pp[["night_rmssd_ms", k]].dropna() if k in pp else pd.DataFrame()
        if len(d) >= 8:
            rho, p = spearmanr(d["night_rmssd_ms"], d[k])
            explore[f"night_rmssd_vs_{k}"] = {"n": int(len(d)), "spearman_rho": round(float(rho), 3), "p_value": round(float(p), 3)}
    report = {
        "model_id": "sleep_hrv", "dataset": "MMASH v1.0.0", "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_type": "signal-processing verification (no model training)",
        "hr_from_rr_vs_actigraph": {"people": int(len(hr)), "minutes": int(hr["minutes"].sum()) if len(hr) else 0,
                                    "median_mae_bpm": round(float(hr["mae_bpm"].median()), 2) if len(hr) else None,
                                    "median_bias_bpm": round(float(hr["bias_bpm"].median()), 2) if len(hr) else None,
                                    "median_r": round(float(hr["r"].median()), 3) if len(hr) else None},
        "sleep_efficiency_recomputed": {"people": int(len(sl)),
                                        "max_abs_diff_pct_points": round(float((sl["reported_eff"] - sl["recomputed_eff"]).abs().max()), 2) if len(sl) else None,
                                        "mean_tst_h": round(float(sl["tst_h"].mean()), 2) if len(sl) else None},
        "night_hrv": {"people_with_valid_night": int(pp["night_rmssd_ms"].notna().sum()),
                      "rmssd_ms_median": round(float(pp["night_rmssd_ms"].median()), 1),
                      "rmssd_ms_iqr": [round(float(pp["night_rmssd_ms"].quantile(q)), 1) for q in (0.25, 0.75)],
                      "median_kept_pct": round(float(pp["kept_pct"].median()), 1)},
        "exploratory_correlations": explore,
        "limitations": ["22 healthy young men, one day each: verification only, no generalisable model.",
                        "Correlations are exploratory, uncorrected for multiple comparisons.",
                        "Earth data; not validated on astronauts."],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=1), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), indent=1))
