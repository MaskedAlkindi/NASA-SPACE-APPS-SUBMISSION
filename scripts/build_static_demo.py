"""Record the demo API into JSON files for the static (Vercel) web demo.

Runs the real backend in-process on a fresh SQLite database, signs in as each demo
account, calls every GET endpoint the website reads, and writes one JSON file per
account to web/static-demo/. The Vercel build serves those files instead of an API.

    python scripts/build_static_demo.py

AI pages (assistant, model registry, fine-tuning) are not recorded: on Vercel they
show "Unavailable, use the desktop app".
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "static-demo"

tmp = Path(tempfile.mkdtemp(prefix="health01-static-"))
os.environ.update({
    "DATABASE_URL": f"sqlite:///{(tmp / 'demo.db').as_posix()}",
    "NASA_ONLINE": "false",
    "DEMO_MODE": "true",
    "ASSISTANT_PROVIDER": "offline",
    "OLLAMA_BASE_URL": "http://127.0.0.1:9",
    "OPENAI_API_KEY": "",
})
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
os.chdir(ROOT / "backend")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

GLOBAL = [
    "/auth/demo-accounts", "/health", "/mission", "/astronauts", "/environment?hours=24", "/modules", "/models",
    "/challenge", "/research/datasets", "/research/findings", "/exercise/catalog", "/exercise/config",
    "/exercise/tracking-spec", "/nutrition/foods", "/simulation/scenarios", "/simulation/status", "/mqtt",
    "/devices", "/servers/connectors", "/servers", "/admin/crew",
]


def per_astronaut(aid: str) -> list[str]:
    today = date.today()
    months = [(today.year, today.month)]
    for _ in range(2):
        y, m = months[-1]
        months.append((y - 1, 12) if m == 1 else (y, m - 1))
    return [
        f"/astronauts/{aid}/summary",
        f"/astronauts/{aid}/measurements?resolution=daily&days=45",
        f"/astronauts/{aid}/measurements?metric=heart_rate&days=5",
        f"/astronauts/{aid}/predictions",
        f"/astronauts/{aid}/alerts?include_environment=false&limit=12",
        f"/astronauts/{aid}/alerts?include_acknowledged=true",
        f"/astronauts/{aid}/risks",
        f"/exercise/astronauts/{aid}/progress",
        f"/exercise/astronauts/{aid}/program",
        f"/exercise/astronauts/{aid}/sessions",
        f"/exercise/astronauts/{aid}/recommendations",
        f"/exercise/astronauts/{aid}/profile",
        *[f"/exercise/astronauts/{aid}/calendar?year={y}&month={m}" for y, m in months],
        f"/ai/astronauts/{aid}/exercise-guidance",
        f"/ai/astronauts/{aid}/assessments",
        f"/nutrition/astronauts/{aid}/day?on={today.isoformat()}",
        f"/nutrition/astronauts/{aid}/day",
        f"/nutrition/astronauts/{aid}/history?days=14",
    ]


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    with TestClient(app) as c:
        pub = c.post("/api/v1/auth/public").json()
        # The NASA OSDR import runs in the background at startup; wait for it.
        h0 = {"Authorization": f"Bearer {pub['access_token']}"}
        for _ in range(120):
            if c.get("/api/v1/research/datasets", headers=h0).json().get("datasets"):
                break
            time.sleep(1)
        accounts = c.get("/api/v1/auth/demo-accounts").json()["accounts"]
        users = {}
        for acc in accounts:
            r = c.post("/api/v1/auth/demo-switch", json={"username": acc["username"]})
            if r.status_code != 200:
                print("skip account", acc["username"], r.status_code)
                continue
            tok, user = r.json()["access_token"], r.json()["user"]
            users[user["username"]] = user
            h = {"Authorization": f"Bearer {tok}"}
            get = lambda p: c.get("/api/v1" + p, headers=h)  # noqa: E731
            crew = get("/astronauts").json().get("astronauts", [])
            paths = list(GLOBAL)
            for a in crew:
                paths += per_astronaut(a["id"])
            for d in (get("/research/datasets").json() or {}).get("datasets", []):
                acc_id = d.get("accession")
                if acc_id:
                    paths.append(f"/research/datasets/{acc_id}/observations")
            data, missing = {}, []
            for p in paths:
                r = get(p)
                if r.status_code == 200:
                    data[p] = r.json()
                else:
                    missing.append(f"{p} {r.status_code}")
            (OUT / f"{user['username']}.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
            size = (OUT / f"{user['username']}.json").stat().st_size / 1e6
            print(f"{user['username']}: {len(data)} responses, {size:.1f} MB" + (f", missing {missing}" if missing else ""))
        index = {"public": pub["user"]["username"], "users": users, "recorded_at": date.today().isoformat()}
        (OUT / "index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
