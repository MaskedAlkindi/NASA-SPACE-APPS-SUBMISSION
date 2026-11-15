"""Downloaders for the Stanford smartwatch illness data, CGMacros, MMASH and CVES sit-to-stand.

    python -m ai.datasets.others download <stanford|cgmacros|mmash|cves>

Each writes data/external/<name>/PROVENANCE.json. Data is used for research
evaluation only and is not redistributed in this repository.
"""
from __future__ import annotations

import re
import subprocess
import sys
import zipfile
from pathlib import Path

from ai.datasets.common import curl, dataset_dir, write_provenance

SOURCES = {
    "stanford_illness": {
        "dataset": "Stanford smartwatch COVID-19 wearables data (Mishra et al.)",
        "url": "https://storage.googleapis.com/gbsc-gcp-project-ipop_public/COVID-19/COVID-19-Wearables.zip",
        "source": "https://medrxiv.org/content/10.1101/2020.07.06.20147512v1 (data link in the preprint)",
        "citation": "Mishra T. et al. Pre-symptomatic detection of COVID-19 from smartwatch data. "
                    "Nat Biomed Eng 4, 1208-1220 (2020). doi:10.1038/s41551-020-00640-6",
        "license": "No explicit licence published with the file; released publicly by the authors for research. "
                   "Used for evaluation only; not redistributed.",
        "population": "Fitbit/other smartwatch users, USA (Earth, not astronauts)",
    },
    "cgmacros": {
        "dataset": "CGMacros v1.0.0", "url": "https://physionet.org/files/cgmacros/1.0.0/CGMacros_dateshifted365.zip?download",
        "extra": ["https://physionet.org/files/cgmacros/1.0.0/DataDictionary_Bio.csv?download",
                  "https://physionet.org/files/cgmacros/1.0.0/DataDictionary_CGMacros-00X.csv?download"],
        "source": "https://physionet.org/content/cgmacros/1.0.0/",
        "citation": "Gutierrez-Osuna R. et al. CGMacros: a scientific dataset for personalized nutrition and diet monitoring "
                    "(PhysioNet, 2025). Goldberger A. et al. PhysioNet, Circulation 2000.",
        "license": "CC BY-NC-SA 4.0 (PhysioNet open access)",
        "population": "45 adults: 15 no diabetes, 16 pre-diabetes, 14 type 2 diabetes (Earth)",
    },
    "mmash": {
        "dataset": "MMASH v1.0.0",
        "url": "https://physionet.org/static/published-projects/mmash/multilevel-monitoring-of-activity-and-sleep-in-healthy-people-1.0.0.zip",
        "source": "https://physionet.org/content/mmash/1.0.0/",
        "citation": "Rossi A. et al. MMASH (PhysioNet, 2020), doi:10.13026/cerq-fc86",
        "license": "Open Data Commons Open Database License v1.0 (ODbL)",
        "population": "22 healthy young men, 24 h (Earth)",
    },
    "cves": {
        "dataset": "Cerebral Vasoregulation in Elderly with Stroke v1.0.0 - sit-to-stand subset",
        "url": "https://physionet-open.s3.amazonaws.com/?list-type=2&prefix=cves/1.0.0/data/sit-stand/",
        "source": "https://physionet.org/content/cves/1.0.0/",
        "citation": "Novak V. et al. Cerebral Vasoregulation in Elderly with Stroke (PhysioNet). Goldberger A. et al. "
                    "PhysioNet, Circulation 2000.",
        "license": "Open Data Commons Attribution License v1.0 (ODC-By)",
        "population": "older adults with and without stroke / hypertension (Earth)",
    },
}


def _unzip(zpath: Path, dest: Path, skip=(".jpg", ".jpeg", ".png", ".heic")) -> list[Path]:
    out = []
    with zipfile.ZipFile(zpath) as z:
        for m in z.infolist():
            if m.is_dir() or m.filename.lower().endswith(skip):
                continue
            target = dest / m.filename
            if not target.resolve().is_relative_to(dest.resolve()):   # zip-slip guard
                continue
            if not target.exists() or target.stat().st_size != m.file_size:
                z.extract(m, dest)
            out.append(target)
    return out


def download(name: str) -> dict:
    meta = SOURCES[name]
    d = dataset_dir(name)
    files: list[Path] = []
    if name == "cves":
        listing = subprocess.run(["curl", "-sSL", "--fail", "-m", "120", meta["url"]], capture_output=True, text=True).stdout
        keys = re.findall(r"<Key>([^<]+)</Key>", listing) + ["cves/1.0.0/subjects.csv"]
        for k in keys:
            dest = d / Path(k).name
            if not dest.exists():
                curl("https://physionet-open.s3.amazonaws.com/" + k, dest)
            files.append(dest)
    else:
        z = d / "download.zip"
        if not z.exists():
            curl(meta["url"], z, timeout=3600)
        files += _unzip(z, d / "raw")
        for u in meta.get("extra", []):
            dest = d / Path(u.split("?")[0]).name
            if not dest.exists():
                curl(u, dest)
            files.append(dest)
        files.append(z)
    return write_provenance(name, {k: v for k, v in meta.items() if k != "extra"}, files)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "download":
        r = download(sys.argv[2])
        print(sys.argv[2], len(r["files"]), "files", round(sum(f["bytes"] for f in r["files"]) / 1e6, 1), "MB")
