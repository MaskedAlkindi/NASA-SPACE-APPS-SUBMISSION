"""NASA Open Science Data Repository research module.

Produces plain data (dataset metadata, parsed observations, computed findings).
Persistence is done by the research service, so this module stays DB-agnostic.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from statistics import mean
from typing import Any

from app.modules.base import HealthModule
from app.modules.nasa_osdr.catalog import CURATED_DATASETS, DISCOVERY_TERMS, OSDR_LICENSE
from app.modules.nasa_osdr.client import OSDRClient, OSDRUnavailable
from app.modules.nasa_osdr.parser import parse_long_csv
from app.schemas.measurement import DataClass

log = logging.getLogger("hmt.osdr")


def _comment(meta_study: dict, name: str) -> str:
    for c in meta_study.get("comments", []) or []:
        if c.get("name") == name and c.get("value"):
            return str(c["value"])
    return ""


def metadata_record(accession: str, meta: dict, files: dict, relevance: str) -> dict:
    study_root = meta.get("study", {}).get(accession, {})
    st = (study_root.get("studies") or [{}])[0]
    pubs = st.get("publications") or study_root.get("publications") or []
    doi = next((p.get("doi") for p in pubs if p.get("doi")), "")
    citation = ""
    if pubs:
        p = pubs[0]
        authors = (p.get("authorList") or "").split(",")
        citation = f"{authors[0].strip()} et al. {p.get('title', '')}".strip()
    organisms = set()
    for src in (st.get("materials", {}) or {}).get("sources", []) or []:
        for ch in src.get("characteristics", []) or []:
            if "organism" in str(ch.get("category", "")).lower():
                v = ch.get("value")
                organisms.add(v.get("annotationValue") if isinstance(v, dict) else str(v))
    assays = sorted({str(a.get("measurementType", {}).get("annotationValue", "")) for a in st.get("assays", []) or []} - {""})
    flist = []
    for f in files.get("studies", {}).get(accession, {}).get("study_files", []):
        flist.append({"name": f["file_name"], "size": f.get("file_size"), "category": f.get("category"),
                      "restricted": bool(f.get("restricted"))})
    return {
        "accession": accession, "title": st.get("title", accession),
        "description": (st.get("description") or "")[:4000],
        "organism": ", ".join(sorted(o for o in organisms if o)) or "",
        "mission": _comment(st, "Mission Name"), "project_type": _comment(st, "Project Type"),
        "assay_types": ", ".join(assays), "release_date": st.get("publicReleaseDate", ""),
        "source_url": f"https://osdr.nasa.gov/bio/repo/data/studies/{accession}", "license": OSDR_LICENSE,
        "doi": doi or "", "citation": citation[:500], "relevance": relevance, "files": flist,
        "extra": {"mission_start": _comment(st, "Mission Start"), "mission_end": _comment(st, "Mission End")},
    }


def compute_findings(accession: str, observations: list[dict], source_file: str) -> list[dict]:
    """Descriptive pre-flight vs first post-flight comparison per analyte. No inference/testing."""
    by = defaultdict(lambda: defaultdict(dict))   # analyte -> subject -> timepoint -> value
    units = {}
    ranges = {}
    for o in observations:
        by[o["analyte"]][o["subject_id"]][o["timepoint"]] = o["value"]
        units[o["analyte"]] = o["unit"]
        if o.get("range_min") is not None:
            ranges[o["analyte"]] = (o.get("range_min"), o.get("range_max"))
    findings = []
    for analyte, subjects in by.items():
        changes = []
        for sid, tps in subjects.items():
            pre = [v for t, v in tps.items() if t.upper().startswith("L-")]
            post1 = tps.get("R+1")
            if pre and post1 is not None and mean(pre) != 0:
                changes.append((sid, mean(pre), post1, (post1 - mean(pre)) / abs(mean(pre)) * 100))
        if len(changes) < 3:
            continue
        pct = [c[3] for c in changes]
        avg = mean(pct)
        same_dir = max(sum(p > 0 for p in pct), sum(p < 0 for p in pct))
        notable = abs(avg) >= 10 and same_dir >= len(pct) - 1
        findings.append({
            "id": f"{accession}-{analyte}".lower().replace(" ", "_")[:80],
            "topic": "research_lab", "accession": accession, "analyte": analyte, "unit": units.get(analyte, ""),
            "n_subjects": len(changes), "mean_pct_change_R+1_vs_preflight": round(avg, 1),
            "subjects_same_direction": same_dir, "notable": notable,
            "per_subject": [{"subject": s, "preflight_mean": round(a, 3), "R+1": round(b, 3), "pct": round(p, 1)}
                            for s, a, b, p in changes],
            "reference_range": ranges.get(analyte), "source_file": source_file,
        })
    return findings


class NasaOSDRModule(HealthModule):
    module_id = "nasa_osdr"
    version = "1.0.0"
    name = "NASA Open Science Data Repository"
    description = "Imports public NASA OSDR study metadata and Inspiration4 crew clinical lab panels for research context."
    category = "research"
    data_class = DataClass.research
    supported_metrics: list[str] = []
    accepts_ingest = False

    def __init__(self, config=None, client: OSDRClient | None = None):
        super().__init__(config)
        self.client = client
        self.last_import: dict[str, Any] | None = None

    def default_config(self) -> dict[str, Any]:
        return {"curated_datasets": [d["accession"] for d in CURATED_DATASETS], "discovery_terms": DISCOVERY_TERMS,
                "api": "https://osdr.nasa.gov/osdr/data/ (public, no key)"}

    def status(self) -> dict[str, Any]:
        if self.client is None:
            return {"state": "unavailable", "detail": "client not configured"}
        if self.last_import is None:
            return {"state": "available", "detail": "not yet imported"}
        li = self.last_import
        state = "connected" if not li["errors"] else "degraded"
        return {"state": state, "detail": f"{li['datasets']} datasets, {li['observations']} observations, "
                                          f"origin={','.join(sorted(li['origins'])) or 'n/a'}",
                "errors": li["errors"][:5]}

    def run_import(self, refresh: bool = False, discover: bool = True) -> dict[str, Any]:
        datasets, observations, findings, errors, origins = [], [], [], [], set()
        for ds in CURATED_DATASETS:
            acc = ds["accession"]
            try:
                meta = self.client.study_metadata(acc, refresh)
                files = self.client.study_files(acc, refresh)
                rec = metadata_record(acc, meta, files, ds["relevance"])
                rec["status"] = "metadata_only"
                rec["extra"]["topics"] = ds["topics"]
                rec["organism"] = rec["organism"] or ds.get("organism", "")
            except OSDRUnavailable as e:
                errors.append(f"{acc}: metadata unavailable ({e})")
                continue
            downloaded = []
            for fname in ds["files"]:
                restricted = next((f["restricted"] for f in rec["files"] if f["name"] == fname), False)
                if restricted:
                    errors.append(f"{acc}/{fname}: restricted - skipped")
                    continue
                try:
                    content, origin = self.client.download(acc, fname, refresh)
                    origins.add(origin)
                except OSDRUnavailable as e:
                    errors.append(f"{acc}/{fname}: {e}")
                    continue
                rows, notes = parse_long_csv(content)
                errors += [f"{acc}/{fname}: {n}" for n in notes if n.startswith("unsupported")]
                for r in rows:
                    r.update(accession=acc, source_file=fname)
                observations += rows
                findings += compute_findings(acc, rows, fname)
                downloaded.append({"file": fname, "rows": len(rows), "origin": origin})
            if downloaded:
                rec["status"] = "downloaded"
            rec["extra"]["downloaded"] = downloaded
            datasets.append(rec)
        if discover:
            seen = {d["accession"] for d in datasets}
            for term in DISCOVERY_TERMS:
                try:
                    for src in self.client.search(term, size=15):
                        acc = src.get("Accession") or ""
                        if not acc.startswith("OSD-") or acc in seen:
                            continue
                        seen.add(acc)
                        datasets.append({
                            "accession": acc, "title": src.get("Study Title", acc),
                            "description": (src.get("Study Description") or "")[:2000],
                            "organism": src.get("organism", "") if isinstance(src.get("organism"), str) else "",
                            "mission": (src.get("Mission") or {}).get("Name", "") if isinstance(src.get("Mission"), dict) else "",
                            "project_type": src.get("Project Type", ""),
                            "assay_types": src.get("Study Assay Measurement Type", "") if isinstance(src.get("Study Assay Measurement Type"), str) else "",
                            "release_date": str(src.get("Study Public Release Date", "")),
                            "source_url": f"https://osdr.nasa.gov/bio/repo/data/studies/{acc}",
                            "license": OSDR_LICENSE, "doi": "", "citation": "",
                            "relevance": f"Discovered via OSDR search '{term}' (metadata only)",
                            "status": "metadata_only", "files": [], "extra": {"search_term": term},
                        })
                except OSDRUnavailable as e:
                    errors.append(f"search '{term}': {e}")
                    break   # offline - do not hammer the API
        self.last_import = {"datasets": len(datasets), "observations": len(observations),
                            "errors": errors, "origins": origins}
        return {"datasets": datasets, "observations": observations, "findings": findings,
                "errors": errors, "origins": sorted(origins)}
