"""Shared helpers for dataset downloaders: provenance records, checksums, retries.

Raw data goes to data/external/<dataset>/ (git-ignored). Each downloader writes
data/external/<dataset>/PROVENANCE.json with source URLs, licence, retrieval time,
and per-file size + SHA-256, so results can be traced to the exact files used.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = Path(os.getenv("HMT_EXTERNAL_DATA", ROOT / "data" / "external"))


def dataset_dir(name: str) -> Path:
    p = EXTERNAL / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def curl(url: str, dest: Path, tries: int = 4, timeout: int = 1800) -> None:
    """Download with curl (uses the OS certificate store; never disables verification)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    last = ""
    for i in range(tries):
        r = subprocess.run(["curl", "-sSL", "--fail", "-m", str(timeout), "-o", str(tmp), url],
                           capture_output=True, text=True)
        if r.returncode == 0 and tmp.exists():
            tmp.replace(dest)
            return
        last = r.stderr.strip()
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"download failed: {url}: {last}")


def curl_json(url: str) -> dict:
    r = subprocess.run(["curl", "-sSL", "--fail", "-m", "120", url], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{url}: {r.stderr.strip()}")
    return json.loads(r.stdout)


def write_provenance(name: str, meta: dict, files: list[Path]) -> dict:
    d = dataset_dir(name)
    rec = {**meta, "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "files": [{"path": str(f.relative_to(d)).replace("\\", "/"), "bytes": f.stat().st_size,
                      "sha256": sha256_file(f)} for f in sorted(files)]}
    (d / "PROVENANCE.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")
    return rec


def provenance(name: str) -> dict | None:
    p = EXTERNAL / name / "PROVENANCE.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
