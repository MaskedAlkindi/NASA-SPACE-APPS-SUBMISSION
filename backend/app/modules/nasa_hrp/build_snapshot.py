"""Download the official challenge resources and build the bundled snapshot.

    cd backend && PYTHONPATH=..:. python -m app.modules.nasa_hrp.build_snapshot

Writes data/challenge_snapshot/{manifest.json, pages.json, evidence.json}.
PDFs are cached in data/challenge_cache/ (not committed; ~25 MB) and recorded in the
manifest with size and SHA-256. Exits non-zero if any resource fails or any evidence
quote cannot be found in its source.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from app.core.config import REPO_ROOT
from app.modules.nasa_hrp.evidence import EVIDENCE
from app.modules.nasa_hrp.extract import normalise, page_sections, pdf_pages
from app.modules.nasa_hrp.sources import (CSA_LICENSE, DOCUMENT_PATTERN, NASA_LICENSE, RESOURCES, SUBPAGE_PATTERN)

OUT = Path(REPO_ROOT) / "data" / "challenge_snapshot"
CACHE = Path(REPO_ROOT) / "data" / "challenge_cache"
UA = {"User-Agent": "Mozilla/5.0 (compatible; health-monitoring-tool-prototype)"}


def fetch(client: httpx.Client, url: str, tries: int = 3) -> httpx.Response:
    last = None
    for i in range(tries):
        try:
            r = client.get(url)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}"
        except httpx.HTTPError as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def doc_name(url: str) -> str:
    return unquote(Path(urlparse(url).path).name).replace(" ", "_")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    client = httpx.Client(timeout=60, follow_redirects=True, headers=UA)
    errors: list[str] = []
    manifest = {"generated_at": now, "challenge_resources_tab": "see sources.RESOURCES_TAB",
                "resources": [], "subpages": [], "documents": [],
                "datasets": [], "datasets_note": "The Resources tab contains no downloadable datasets. "
                "Studies described there (e.g. Spaceflight Standard Measures, CIPHER, Omics Archive) keep crew data "
                "in controlled-access archives that require a formal data request."}
    pages: dict[str, dict] = {}
    texts: dict[str, str] = {}         # source key -> normalised text for evidence checks
    pdf_texts: dict[str, list[str]] = {}
    sub_urls: set[str] = set()
    doc_urls: set[str] = set()

    for res in RESOURCES:
        try:
            r = fetch(client, res["url"])
        except RuntimeError as e:
            errors.append(str(e))
            manifest["resources"].append({**res, "status": "unreachable"})
            continue
        sec = page_sections(r.text)
        lic = NASA_LICENSE if res["agency"] == "NASA" else CSA_LICENSE
        manifest["resources"].append({**res, "status": "downloaded", "bytes": len(r.content), "sha256": sha(r.content),
                                      "license": lic, "kind": "web page", "retrieved_at": now})
        texts[res["id"]] = normalise(sec["text"])
        if res["agency"] == "NASA":
            pages[res["id"]] = {"url": res["url"], "title": sec["title"], "sections": sec["sections"], "agency": "NASA"}
            sub_urls |= {m.group(0) for m in re.finditer(SUBPAGE_PATTERN, r.text)}
        else:
            # Crown copyright: keep title + link only; facts are verified against the text but not stored in full.
            pages[res["id"]] = {"url": res["url"], "title": sec["title"] or res["title"], "agency": "CSA", "sections": {}}
        time.sleep(1)

    sub_urls = {u for u in sub_urls if re.fullmatch(SUBPAGE_PATTERN, u)}
    for url in sorted(sub_urls):
        slug = url.rstrip("/").split("/")[-1]
        try:
            r = fetch(client, url)
        except RuntimeError as e:
            errors.append(str(e))
            manifest["subpages"].append({"slug": slug, "url": url, "status": "unreachable"})
            continue
        sec = page_sections(r.text)
        pages[slug] = {"url": url, "title": sec["title"], "sections": sec["sections"], "agency": "NASA"}
        texts[slug] = normalise(sec["text"])
        docs = {u for u in sec["links"] if re.fullmatch(DOCUMENT_PATTERN, u.split("?")[0])}
        doc_urls |= docs
        manifest["subpages"].append({"slug": slug, "url": url, "title": sec["title"], "status": "downloaded",
                                     "bytes": len(r.content), "sha256": sha(r.content), "license": NASA_LICENSE,
                                     "linked_documents": sorted(d.split("?")[0] for d in docs)})
        time.sleep(0.8)

    for url in sorted(doc_urls):
        clean = url.split("?")[0]
        name = doc_name(clean)
        try:
            r = fetch(client, url)
            data = r.content
            (CACHE / name).write_bytes(data)
            ptxt = pdf_pages(data)
            pdf_texts[name] = ptxt
            first = next((p for p in ptxt if p.strip()), "")
            manifest["documents"].append({"file": name, "url": clean, "status": "downloaded+parsed", "bytes": len(data),
                                          "sha256": sha(data), "pages": len(ptxt), "chars": sum(map(len, ptxt)),
                                          "opening_text": first[:300], "license": NASA_LICENSE})
        except Exception as e:   # noqa: BLE001 - record and continue
            errors.append(f"{clean}: {e}")
            manifest["documents"].append({"file": name, "url": clean, "status": "unreachable"})
        time.sleep(1)

    # ---- verify evidence quotes -------------------------------------------------
    resolved = []
    for ev in EVIDENCE:
        anchor = normalise(ev["anchor"])
        src = ev["source"]
        found = None
        if src in pdf_texts:
            for i, p in enumerate(pdf_texts[src], start=1):
                if anchor in normalise(p):
                    doc = next(d for d in manifest["documents"] if d["file"] == src)
                    found = {"source_type": "pdf", "source_url": doc["url"], "page": i}
                    break
        elif src in texts:
            if anchor in texts[src]:
                url = pages.get(src, {}).get("url") or next(r["url"] for r in RESOURCES if r["id"] == src)
                found = {"source_type": "web page", "source_url": url, "page": None}
        if not found:
            errors.append(f"evidence '{ev['id']}': quote not found in {src}")
            continue
        resolved.append({**{k: v for k, v in ev.items()}, **found, "quote": ev["anchor"], "verified_at": now})

    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "pages.json").write_text(json.dumps(pages, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "evidence.json").write_text(json.dumps(resolved, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"resources={len(manifest['resources'])} subpages={len(manifest['subpages'])} "
          f"documents={len(manifest['documents'])} evidence={len(resolved)}/{len(EVIDENCE)}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
