"""PMData (Simula, 2020): 16 people, ~5 months, Fitbit Versa 2 + PMSys wellness self-reports.

Source:   https://datasets.simula.no/pmdata  ->  OSF https://osf.io/vx4bk
Paper:    Thambawita et al., "PMData: A Sports Logging Dataset", MMSys '20, doi:10.1145/3339825.3394926
Licence:  CONFLICT. The Simula page states CC BY 4.0; the licence.txt in the OSF repository states
          CC BY-NC 4.0. We follow the stricter CC BY-NC 4.0 (non-commercial use, attribution).

Only the daily-level files needed by the models are downloaded (the minute-level heart_rate.json
is ~120 MB per person and is not needed). Steps are minute-level and summed per day.

    python -m ai.datasets.pmdata download
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from ai.datasets.common import curl, curl_json, dataset_dir, provenance, write_provenance

NAME = "pmdata"
OSF_ROOT = "https://api.osf.io/v2/nodes/vx4bk/files/osfstorage/5e99d05ef135350590d5316d/"
WANTED = {
    "pmsys": ["wellness.csv", "srpe.csv"],
    "fitbit": ["resting_heart_rate.json", "sleep.json", "sleep_score.csv", "sedentary_minutes.json",
               "lightly_active_minutes.json", "moderately_active_minutes.json", "very_active_minutes.json",
               "steps.json", "exercise.json"],
}
META = {
    "dataset": "PMData", "source": "https://datasets.simula.no/pmdata", "repository": "https://osf.io/vx4bk",
    "citation": "Thambawita V. et al. PMData: A Sports Logging Dataset. MMSys '20. doi:10.1145/3339825.3394926",
    "license": "CC BY-NC 4.0 (OSF licence.txt). Simula page states CC BY 4.0; stricter terms applied.",
    "subjects": 16, "population": "healthy adults, Norway (Earth, not astronauts)",
}


def _list(url: str) -> list[dict]:
    out = []
    while url:
        d = curl_json(url)
        out += d["data"]
        url = d["links"].get("next")
    return out


def download() -> dict:
    d = dataset_dir(NAME)
    files: list[Path] = []
    for p in _list(OSF_ROOT):
        if p["attributes"]["kind"] != "folder":
            continue
        pid = p["attributes"]["name"]
        for sub in _list(p["relationships"]["files"]["links"]["related"]["href"]):
            folder = sub["attributes"]["name"]
            if folder not in WANTED:
                continue
            for f in _list(sub["relationships"]["files"]["links"]["related"]["href"]):
                name = f["attributes"]["name"]
                if name in WANTED[folder]:
                    dest = d / pid / folder / name
                    if not dest.exists() or dest.stat().st_size != f["attributes"]["size"]:
                        curl(f["links"]["download"], dest)
                    files.append(dest)
                    print("ok", pid, folder, name, flush=True)
    return write_provenance(NAME, META, files)


# ------------------------------------------------------------------ loading
def _jload(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _daily_series(path: Path, name: str) -> pd.Series:
    rows = _jload(path)
    if not rows:
        return pd.Series(dtype=float, name=name)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["dateTime"]).dt.normalize()
    return pd.to_numeric(df["value"], errors="coerce").groupby(df["date"]).sum().rename(name)


def load_participant(pid: str) -> pd.DataFrame:
    """One row per day with wellness labels and wearable features. Missing values stay NaN."""
    base = dataset_dir(NAME) / pid
    well = pd.read_csv(base / "pmsys" / "wellness.csv")
    well["date"] = pd.to_datetime(well["effective_time_frame"], utc=True).dt.tz_localize(None).dt.normalize()
    well = well.groupby("date")[["fatigue", "mood", "readiness", "sleep_duration_h", "sleep_quality", "soreness", "stress"]].mean()

    rhr_rows = _jload(base / "fitbit" / "resting_heart_rate.json")
    rhr = pd.Series({pd.to_datetime(r["dateTime"]).normalize(): r["value"].get("value") for r in rhr_rows}, dtype=float)
    rhr = rhr.where(rhr > 0).rename("resting_hr")

    sleep_rows = [s for s in _jload(base / "fitbit" / "sleep.json") if s.get("mainSleep")]
    sl = pd.DataFrame([{"date": pd.to_datetime(s["dateOfSleep"]).normalize(), "sleep_min": s.get("minutesAsleep"),
                        "sleep_eff": s.get("efficiency"),
                        "sleep_start_h": (pd.to_datetime(s["startTime"]).hour + pd.to_datetime(s["startTime"]).minute / 60)}
                       for s in sleep_rows])
    sl = sl.groupby("date").last() if not sl.empty else pd.DataFrame(columns=["sleep_min", "sleep_eff", "sleep_start_h"])

    sc = pd.read_csv(base / "fitbit" / "sleep_score.csv") if (base / "fitbit" / "sleep_score.csv").exists() else pd.DataFrame()
    if not sc.empty:
        sc["date"] = pd.to_datetime(sc["timestamp"], utc=True).dt.tz_localize(None).dt.normalize()
        sc = sc.groupby("date")[["overall_score", "deep_sleep_in_minutes", "restlessness"]].mean()

    act = pd.concat([_daily_series(base / "fitbit" / f"{k}_minutes.json", k) for k in
                     ("sedentary", "lightly_active", "moderately_active", "very_active")], axis=1)
    steps = _daily_series(base / "fitbit" / "steps.json", "steps")

    srpe = pd.read_csv(base / "pmsys" / "srpe.csv") if (base / "pmsys" / "srpe.csv").exists() else pd.DataFrame()
    if not srpe.empty:
        srpe["date"] = pd.to_datetime(srpe["end_date_time"], utc=True).dt.tz_localize(None).dt.normalize()
        srpe["load"] = pd.to_numeric(srpe["perceived_exertion"], errors="coerce") * pd.to_numeric(srpe["duration_min"], errors="coerce")
        load = srpe.groupby("date")["load"].sum().rename("training_load")
    else:
        load = pd.Series(dtype=float, name="training_load")

    df = pd.concat([well, rhr, sl, sc if not sc.empty else None, act, steps, load], axis=1).sort_index()
    df.index.name = "date"
    df["training_load"] = df["training_load"].fillna(0.0)   # no logged session = no training load
    df["participant"] = pid
    return df.reset_index()


def load_all() -> pd.DataFrame:
    if provenance(NAME) is None:
        raise FileNotFoundError("PMData not downloaded: python -m ai.datasets.pmdata download")
    pids = sorted(p.name for p in dataset_dir(NAME).iterdir() if p.is_dir() and p.name.startswith("p"))
    return pd.concat([load_participant(p) for p in pids], ignore_index=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["download"]:
        r = download()
        print(f"{len(r['files'])} files, {sum(f['bytes'] for f in r['files']) / 1e6:.1f} MB")
    else:
        df = load_all()
        print(df.describe(include="all").T.head(40))
        print(np.round(df.notna().mean(), 2))
