"""Model B - evaluate illness / physiological anomaly detection on the Stanford smartwatch data.

Data:   COVID-19-Wearables.zip (Mishra et al., Nat Biomed Eng 2020) - minute/second-level HR, steps, sleep.
Labels: Supplementary Table 3 (COVID-19 symptom-onset dates) and Supplementary Table 4 (self-reported other
        illnesses with sick start/end dates) of the same paper. Dates are shifted consistently by the authors.

Resting heart rate (RHR) follows the paper: heart rate in minutes with zero steps in the preceding 12 minutes.
Detectors (all use only data before the day they score - no look-ahead):
  rhr_z          daily RHR vs personal baseline (median / scaled MAD of the previous 28 days)
  rhr_z_actadj   same, after removing the person's own RHR~steps relationship learned on past days
  legacy_iforest the tool's existing anomaly model (resting HR, sleep, steps; HRV is not in this data)
Event-level sensitivity: an illness event counts as detected if an alert occurs from 7 days before to
7 days after symptom onset (the paper's pre-symptomatic window and early symptomatic phase).
Specificity: on "healthy days" - every day at least 21 days away from any reported illness or COVID period.
Thresholds are selected on a random half of the participants and reported on the other half.

    python -m ai.evaluation.stanford_illness
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ai.datasets.common import dataset_dir, provenance
from ai.preprocessing.signals import causal_baseline

D = dataset_dir("stanford_illness")
RAW = D / "raw" / "COVID-19-Wearables"
CACHE = D / "derived_daily.csv"
REPORT = Path(__file__).resolve().parents[1] / "models" / "illness_rhr" / "report.json"
WINDOW = (-7, 7)
HEALTHY_GAP = 21


# ------------------------------------------------------------------ data
def daily_for(pid: str) -> pd.DataFrame | None:
    hr_f, st_f = RAW / f"{pid}_hr.csv", RAW / f"{pid}_steps.csv"
    if not hr_f.exists() or not st_f.exists():
        return None
    hr = pd.read_csv(hr_f, usecols=["datetime", "heartrate"])
    st = pd.read_csv(st_f, usecols=["datetime", "steps"])
    hr["t"] = pd.to_datetime(hr["datetime"], format="%Y-%m-%d %H:%M:%S", errors="coerce").dt.floor("min")
    st["t"] = pd.to_datetime(st["datetime"], format="%Y-%m-%d %H:%M:%S", errors="coerce").dt.floor("min")
    hr_m = hr.dropna(subset=["t"]).groupby("t")["heartrate"].mean()
    st_m = st.dropna(subset=["t"]).groupby("t")["steps"].sum()
    idx = hr_m.index.union(st_m.index)
    st_full = st_m.reindex(pd.date_range(idx.min(), idx.max(), freq="min"), fill_value=0)
    still = st_full.rolling(12, min_periods=12).sum() == 0
    rest = hr_m[still.reindex(hr_m.index, fill_value=False)]
    rest = rest[(rest > 30) & (rest < 200)]
    day = pd.DataFrame({
        "resting_hr": rest.groupby(rest.index.normalize()).median(),
        "rest_minutes": rest.groupby(rest.index.normalize()).size(),
        "steps": st_m.groupby(st_m.index.normalize()).sum(),
    })
    day = day[day["rest_minutes"] >= 60]         # need at least an hour of resting data to trust the day
    sl_f = RAW / f"{pid}_sleep.csv"
    if sl_f.exists():
        sl = pd.read_csv(sl_f)
        sl["t"] = pd.to_datetime(sl["datetime"], errors="coerce")
        asleep = sl[sl["stage"].isin(["light", "deep", "rem", "asleep"])]
        # attribute sleep to the wake-up day (shift evening starts forward)
        mins = asleep["stage_duration"] / 60
        dates = (asleep["t"] + pd.Timedelta(hours=12)).dt.normalize()
        day["sleep_h"] = (mins.groupby(dates).sum() / 60).reindex(day.index)
    day.index.name = "date"
    day = day.reset_index()
    day["participant"] = pid
    return day


def build_daily(force: bool = False) -> pd.DataFrame:
    if CACHE.exists() and not force:
        return pd.read_csv(CACHE, parse_dates=["date"])
    pids = sorted({f.name.split("_")[0] for f in RAW.glob("*_hr.csv")})
    frames = []
    for i, pid in enumerate(pids):
        d = daily_for(pid)
        if d is not None and len(d):
            frames.append(d)
        print(f"{i + 1}/{len(pids)} {pid} days={0 if d is None else len(d)}", flush=True)
    out = pd.concat(frames, ignore_index=True)
    out.to_csv(CACHE, index=False)
    return out


def _dates(cell) -> list[pd.Timestamp]:
    return [pd.Timestamp(x) for x in re.findall(r"Timestamp\('([^']+)'\)", str(cell))]


def labels() -> tuple[list[dict], dict[str, list[tuple]]]:
    """Return illness events (participant, onset, kind) and per-participant sick periods to exclude from 'healthy'."""
    x = pd.ExcelFile(D / "41551_2020_640_MOESM3_ESM.xlsx")
    t3 = x.parse("SuppTable3_Fig2a_COVID-19", header=3)
    t4 = x.parse("SuppTable4_Fig2a_Illnesses", header=None)
    hdr = next(i for i in range(10) if t4.iloc[i, 0] == "ParticipantID")
    t4.columns = t4.iloc[hdr]
    t4 = t4.iloc[hdr + 1:].dropna(subset=["ParticipantID"])
    events, sick = [], {}
    for _, r in t3.iterrows():
        pid = str(r["ParticipantID"])
        if r["Category"] != "COVID-19":
            continue
        onset = _dates(r["Symptom_dates"]) or _dates(r["covid_diagnosis_dates"])
        if onset:
            o = min(onset)
            rec = _dates(r["recovery_dates"])
            events.append({"participant": pid, "onset": o, "kind": "COVID-19"})
            sick.setdefault(pid, []).append((o - pd.Timedelta(days=14), (max(rec) if rec else o + pd.Timedelta(days=21))))
    for _, r in t4.iterrows():
        pid = str(r["ParticipantID"])
        s, e = pd.to_datetime(r["shift_sick_start"], errors="coerce"), pd.to_datetime(r["shift_sick_end"], errors="coerce")
        if pd.isna(s):
            continue
        events.append({"participant": pid, "onset": s, "kind": "other illness"})
        sick.setdefault(pid, []).append((s - pd.Timedelta(days=14), (e if pd.notna(e) else s + pd.Timedelta(days=14))))
    return events, sick


# ------------------------------------------------------------------ detectors
def scores(df: pd.DataFrame) -> pd.DataFrame:
    out = []
    from ml.models.anomaly import AnomalyDetector
    det = AnomalyDetector()
    for pid, g in df.sort_values("date").groupby("participant"):
        g = g.set_index("date").asfreq("D").reset_index()
        g["participant"] = pid
        b = causal_baseline(g["resting_hr"], window=28, gap=1, min_periods=14)
        g["rhr_z"] = b["z"]
        # activity-adjusted: residual of RHR on (log) steps using a causal rolling OLS fit
        resid = np.full(len(g), np.nan)
        x = np.log1p(g["steps"].to_numpy(float))
        y = g["resting_hr"].to_numpy(float)
        for i in range(len(g)):
            lo = max(0, i - 29)
            xs, ys = x[lo:i], y[lo:i]
            m = ~np.isnan(xs) & ~np.isnan(ys)
            if m.sum() >= 14 and not np.isnan(x[i]) and not np.isnan(y[i]):
                A = np.c_[np.ones(m.sum()), xs[m]]
                coef, *_ = np.linalg.lstsq(A, ys[m], rcond=None)
                r_hist = ys[m] - A @ coef
                s = max(np.median(np.abs(r_hist - np.median(r_hist))) * 1.4826, 0.5)
                resid[i] = (y[i] - (coef[0] + coef[1] * x[i])) / s
        g["rhr_z_actadj"] = resid
        if det.available:
            legacy = pd.DataFrame({"date": g["date"], "resting_heart_rate": g["resting_hr"],
                                   "sleep_duration": g.get("sleep_h"), "steps": g["steps"]})
            res = det.score_days(legacy)
            g["legacy_iforest"] = [r["score"] if r["status"] == "scored" else np.nan for r in res]
            g["legacy_threshold"] = det.threshold
        out.append(g)
    return pd.concat(out, ignore_index=True)


def evaluate(sc: pd.DataFrame, events: list[dict], sick: dict, col: str, thr: float, consec: int, pids: set) -> dict:
    sc = sc[sc["participant"].isin(pids)]
    det_events, leads, n_events = 0, [], 0
    healthy_days = alerts_days = episodes = 0
    for pid, g in sc.groupby("participant"):
        g = g.sort_values("date").reset_index(drop=True)
        flag = (g[col] >= thr).astype(int)
        if consec > 1:
            flag = (flag.rolling(consec).sum() >= consec).astype(int)
        g["alert"] = flag.fillna(0).astype(bool)
        periods = sick.get(pid, [])
        def far(d):
            return all(not (s - pd.Timedelta(days=HEALTHY_GAP - 14) <= d <= e + pd.Timedelta(days=HEALTHY_GAP)) for s, e in periods)
        h = g[g[col].notna() & g["date"].map(far)]
        healthy_days += len(h)
        alerts_days += int(h["alert"].sum())
        episodes += int((h["alert"] & ~h["alert"].shift(1, fill_value=False)).sum())
        for ev in (e for e in events if e["participant"] == pid):
            w = g[(g["date"] >= ev["onset"] + pd.Timedelta(days=WINDOW[0])) & (g["date"] <= ev["onset"] + pd.Timedelta(days=WINDOW[1]))]
            if w[col].notna().sum() < 3:
                continue                      # not enough scored days around onset to judge
            n_events += 1
            hit = w[w["alert"]]
            if len(hit):
                det_events += 1
                leads.append((hit["date"].iloc[0] - ev["onset"]).days)
    return {"detector": col, "threshold": thr, "consecutive_days": consec, "events_evaluable": n_events,
            "sensitivity": round(det_events / n_events, 3) if n_events else None,
            "specificity_day": round(1 - alerts_days / healthy_days, 4) if healthy_days else None,
            "false_alert_episodes_per_30_healthy_days": round(30 * episodes / healthy_days, 3) if healthy_days else None,
            "healthy_days": int(healthy_days),
            "median_days_alert_vs_onset": float(np.median(leads)) if leads else None,
            "pct_detected_before_onset": round(float(np.mean(np.array(leads) < 0)) * 100, 1) if leads else None}


def run() -> dict:
    if provenance("stanford_illness") is None:
        raise FileNotFoundError("python -m ai.datasets.others download stanford_illness")
    daily = build_daily()
    events, sick = labels()
    sc = scores(daily)
    have = set(sc["participant"])
    events = [e for e in events if e["participant"] in have]
    rng = np.random.default_rng(42)
    pids = sorted(have)
    rng.shuffle(pids)
    tune, test = set(pids[: len(pids) // 2]), set(pids[len(pids) // 2:])
    grid = [("rhr_z", t, c) for t in (2.0, 2.5, 3.0, 3.5) for c in (1, 2)] + \
           [("rhr_z_actadj", t, c) for t in (2.0, 2.5, 3.0, 3.5) for c in (1, 2)]
    legacy_thr = float(sc["legacy_threshold"].dropna().iloc[0]) if "legacy_threshold" in sc else None
    if legacy_thr:
        grid += [("legacy_iforest", legacy_thr, 1), ("legacy_iforest", legacy_thr, 2)]
    tuned = [evaluate(sc, events, sick, c, t, k, tune) for c, t, k in grid]
    # selection rule fixed in advance: max sensitivity subject to <= 1 false-alert episode per 30 healthy days
    ok = [r for r in tuned if r["sensitivity"] is not None and (r["false_alert_episodes_per_30_healthy_days"] or 0) <= 1.0]
    best = max(ok, key=lambda r: (r["sensitivity"], r["specificity_day"])) if ok else None
    held_out = evaluate(sc, events, sick, best["detector"], best["threshold"], best["consecutive_days"], test) if best else None
    all_people = [evaluate(sc, events, sick, c, t, k, have) for c, t, k in grid]
    legacy_full = [r for r in all_people if r["detector"] == "legacy_iforest"]
    report = {
        "model_id": "illness_rhr", "dataset": "Stanford COVID-19 wearables (Mishra et al. 2020)",
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "participants_with_daily_data": len(have), "illness_events_with_data": len(events),
        "events_by_kind": pd.Series([e["kind"] for e in events]).value_counts().to_dict(),
        "protocol": {"rhr_definition": "HR in minutes with zero steps in the preceding 12 minutes (paper definition); "
                                       "daily median; days with < 60 resting minutes dropped",
                     "baseline": "previous 28 days, >= 14 days required, robust z (median / scaled MAD)",
                     "event_window_days": list(WINDOW), "healthy_day_gap_days": HEALTHY_GAP,
                     "split": "participants randomly split 50/50 (seed 42); threshold chosen on the tuning half with a "
                              "rule fixed in advance (max sensitivity with <= 1 false-alert episode / 30 healthy days)"},
        "tuning_half": tuned, "selected": best, "held_out_half": held_out,
        "all_participants_grid": all_people, "legacy_iforest_all_participants": legacy_full,
        "limitations": ["Small number of illness events; wide uncertainty on sensitivity.",
                        "Self-reported illness dates; other unreported illnesses may sit in 'healthy' days.",
                        "Earth population, consumer smartwatches; not validated on astronauts.",
                        "Detects physiological change consistent with illness; it does not diagnose illness."],
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    r = run()
    print(json.dumps({k: r[k] for k in ("participants_with_daily_data", "illness_events_with_data", "events_by_kind",
                                        "selected", "held_out_half", "legacy_iforest_all_participants")}, indent=1, default=str))
