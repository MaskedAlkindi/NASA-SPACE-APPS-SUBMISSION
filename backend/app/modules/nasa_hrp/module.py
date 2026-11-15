"""NASA Human Research Program knowledge from the official challenge Resources tab.

Loads the verified snapshot in data/challenge_snapshot (built by build_snapshot.py)
and exposes the five hazards, the 17 HRP risks (with NASA's own prevention text),
and quantitative evidence with page-level citations.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT
from app.modules.base import HealthModule
from app.modules.nasa_hrp.evidence import RISK_MONITORING
from app.modules.nasa_hrp.sources import CHALLENGE_INDICATORS, RESOURCES, RESOURCES_TAB, RISK_CATEGORIES
from app.schemas.measurement import DataClass

SNAPSHOT = Path(REPO_ROOT) / "data" / "challenge_snapshot"
HAZARD_SLUGS = ["hazard-space-radiation", "hazard-isolation-and-confinement", "hazard-distance-from-earth",
                "hazard-gravity-fields", "hazard-hostile-closed-environments"]


def _clean(text: str) -> str:
    text = re.sub(r"^Human Spaceflight Hazards\s*", "", text)
    text = re.sub(r"Learn more about[^.]*:.*$", "", text)
    return re.sub(r"\s+", " ", text).strip()


@lru_cache
def load() -> dict[str, Any]:
    if not (SNAPSHOT / "manifest.json").exists():
        return {"available": False}
    manifest = json.loads((SNAPSHOT / "manifest.json").read_text(encoding="utf-8"))
    pages = json.loads((SNAPSHOT / "pages.json").read_text(encoding="utf-8"))
    evidence = json.loads((SNAPSHOT / "evidence.json").read_text(encoding="utf-8"))

    hazards = []
    for slug in HAZARD_SLUGS:
        p = pages.get(slug)
        if not p:
            continue
        text = _clean(" ".join(p["sections"].values()))
        name = p["title"].replace("Hazard: ", "")
        text = re.sub(rf"^.*?Hazard:\s*{re.escape(name)}\s*", "", text, count=1, flags=re.S)
        hazards.append({"slug": slug, "name": name, "url": p["url"], "summary": text[:1200]})

    category_of = {s: c for c, slugs in RISK_CATEGORIES.items() for s in slugs}
    risks = []
    for slug, mon in RISK_MONITORING.items():
        p = pages.get(slug)
        if not p:
            continue
        sec = p["sections"]
        dyk = sec.get("Did you know?", "")
        formal = ""
        m = re.search(r"Formal risk description:\s*(.*?)(?:Research in support|Explore more|$)", dyk)
        if m:
            formal = m.group(1).strip()
            dyk = dyk[:m.start()].strip()
        risks.append({
            "slug": slug, "name": p["title"].replace("Risk of", "Risk of").strip(), "url": p["url"],
            "category": category_of.get(slug, ""), "hazards": mon["hazards"],
            "top_risks": sec.get("What are the top risks?", ""), "what_can_be_done": sec.get("What can be done about it?", ""),
            "did_you_know": dyk, "formal_description": formal,
            "monitoring": mon["monitoring"], "metrics": mon["metrics"], "note": mon.get("note", ""),
            "evidence": [e["id"] for e in evidence if slug in e["risks"]],
        })
    return {"available": True, "manifest": manifest, "pages": pages, "evidence": evidence,
            "hazards": hazards, "risks": risks}


class NasaHRPModule(HealthModule):
    module_id = "nasa_hrp"
    version = "1.0.0"
    name = "NASA challenge resources (HRP hazards & risks)"
    description = ("The official challenge Resources: NASA Human Research Program hazards, risks and research pages, "
                   "linked NASA reports, and CSA articles, with verified page-level evidence.")
    category = "research"
    data_class = DataClass.research
    supported_metrics: list[str] = []
    accepts_ingest = False

    def default_config(self) -> dict[str, Any]:
        return {"resources_tab": RESOURCES_TAB, "resources": [r["title"] for r in RESOURCES],
                "challenge_indicators": CHALLENGE_INDICATORS, "snapshot": "data/challenge_snapshot"}

    def status(self) -> dict[str, Any]:
        k = load()
        if not k["available"]:
            return {"state": "unavailable", "detail": "snapshot missing - run build_snapshot"}
        m = k["manifest"]
        ok = sum(r.get("status") == "downloaded" for r in m["resources"])
        return {"state": "connected" if ok == len(RESOURCES) else "degraded",
                "detail": f"{ok}/{len(RESOURCES)} resources, {len(m['subpages'])} NASA pages, {len(m['documents'])} reports, "
                          f"{len(k['evidence'])} verified facts (snapshot {m['generated_at'][:10]})"}
