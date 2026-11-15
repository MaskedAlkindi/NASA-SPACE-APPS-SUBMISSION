"""Parsers for OSDR clinical lab files (long-format CSV, as published for Inspiration4).

Only values present in the file are produced; nothing is imputed.
"""
from __future__ import annotations

import csv
import io
import re

COLS = {
    "analyte": ["ANALYTE", "Analyte"],
    "value": ["VALUE", "Concentration"],
    "unit": ["UNITS", "Unit"],
    "subject": ["SUBJECT_ID", "ID"],
    "timepoint": ["TEST_DATE", "timepoint", "Timepoint"],
    "range_min": ["RANGE_MIN"],
    "range_max": ["RANGE_MAX"],
}


def phase_of(tp: str) -> str:
    tp = tp.strip().upper()
    if re.fullmatch(r"L-\d+", tp):
        return "preflight"
    if re.fullmatch(r"R\+\d+", tp):
        return "postflight"
    if tp.startswith("FD"):
        return "inflight"
    return "unknown"


def _num(s: str | None) -> float | None:
    if s is None:
        return None
    s = s.strip().replace(",", "")
    if not s or s.upper() in {"NA", "N/A", "NAN", "ND"}:
        return None
    s = s.lstrip("<>")
    try:
        return float(s)
    except ValueError:
        return None


def parse_long_csv(content: bytes) -> tuple[list[dict], list[str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    col = {}
    for key, options in COLS.items():
        col[key] = next((o for o in options if o in header), None)
    missing = [k for k in ("analyte", "value", "subject", "timepoint") if col[k] is None]
    if missing:
        return [], [f"unsupported layout: missing columns {missing} (header={header[:8]})"]
    rows, skipped = [], 0
    for r in reader:
        val = _num(r.get(col["value"]))
        if val is None:
            skipped += 1
            continue
        tp = (r.get(col["timepoint"]) or "").strip()
        rows.append({
            "subject_id": (r.get(col["subject"]) or "").strip(),
            "analyte": (r.get(col["analyte"]) or "").strip(),
            "value": val,
            "unit": (r.get(col["unit"]) or "").strip() if col["unit"] else "",
            "range_min": _num(r.get(col["range_min"])) if col["range_min"] else None,
            "range_max": _num(r.get(col["range_max"])) if col["range_max"] else None,
            "timepoint": tp, "phase": phase_of(tp),
        })
    notes = [f"{skipped} rows without numeric value skipped"] if skipped else []
    return rows, notes
