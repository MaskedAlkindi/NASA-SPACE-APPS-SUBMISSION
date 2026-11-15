"""Write docs/NASA_CHALLENGE_RESOURCES.md from the verified snapshot (data/challenge_snapshot).

    python scripts/write_challenge_doc.py      # from the repository root

Tables (resources, documents, evidence, risk coverage) come from the snapshot so the
document always matches what was actually downloaded and verified.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.modules.nasa_hrp.evidence import RISK_MONITORING  # noqa: E402
from app.modules.nasa_hrp.sources import CHALLENGE_INDICATORS, RESOURCES_TAB, RISK_CATEGORIES  # noqa: E402

SNAP = ROOT / "data" / "challenge_snapshot"
m = json.loads((SNAP / "manifest.json").read_text(encoding="utf-8"))
pages = json.loads((SNAP / "pages.json").read_text(encoding="utf-8"))
ev = json.loads((SNAP / "evidence.json").read_text(encoding="utf-8"))

USE = {
    "nasa-hrp-hazards": "The five hazards (shown on the Hazards & Risks page; hazard text used by the assistant).",
    "nasa-hrp-risks": "The 17 HRP risks: risk text, NASA's \"What can be done about it?\" guidance, links to evidence reports.",
    "nasa-hrp-ongoing": "Descriptions of ongoing studies (Standard Measures, CIPHER, Omics Archive, Immune Biomarkers...) "
                        "used to choose indicators; links to NASA-STD-3001 technical briefs.",
    "csa-radiation": "Radiation context: neutrons are ~30% of ISS radiation (verified fact).",
    "csa-why-science": "Context only (why ISS research matters; risks of longer missions). No measurements.",
}
DOC_USE = {
    "Fracture.pdf": "Bone-loss rate 1-1.5%/month -> bone projection model.",
    "Nutrition_ER_human_adaptation_2020_final.pdf": "Core temperature +1 °C, body mass -2.4%/100 d, blood volume, urine calcium -> "
                                                     "temperature rule design, body-mass model, simulator calibration.",
    "Cardio_Risk_EB_2022_FINAL_4-3-2023.pdf": "In-flight HR/BP lower than pre-flight, orthostatic intolerance, insulin resistance, "
                                              "ISS/Mars dose ranges -> personal in-flight baselines, glucose caveat, radiation model.",
    "ochmo-tb-030-bone-loss.pdf": "Vitamin D optimal range (NASA-STD-3001 brief) -> bone risk evidence.",
    "Degen.pdf": "Radiation and cardiovascular/degenerative risk background. No fact extracted yet.",
    "ochmo-mtb-007-venous-thrombosis-in-spaceflight.pdf": "Venous thrombosis background (needs ultrasound; not monitorable by the tool).",
    "hrp-rap-for-web-62026.pdf": "HRP Risk Approach Plans (research planning charts). Not measurement data.",
    "hrp-rap-for-web-62026-hfbp.pdf": "Risk Approach Plans, Human Factors & Behavioral Performance. Planning only.",
    "hrp-rap-for-web-62026-hhc.pdf": "Risk Approach Plans, Human Health Countermeasures. Planning only.",
    "hrp-rap-for-web-62026-sr.pdf": "Risk Approach Plans, Space Radiation. Planning only.",
    "160410main_space_training_fact_sheet.pdf": "Astronaut training fact sheet. Not health data; not used.",
    "whatisyourspaceheight.pdf": "Educational activity (spine lengthening in space). Not used.",
}
MON = {"direct": "Measured", "partial": "Partly (related indicators / model)", "clinical": "Needs clinical exam",
       "none": "Not monitored (operational)"}

L: list[str] = []
w = L.append
w("# NASA challenge resources: what they contain and how the tool uses them\n")
w(f"Challenge: *Create Health Monitoring Software for Astronauts on Space Missions* (NASA Space Apps 2026).  ")
w(f"Resources tab: <{RESOURCES_TAB}>  ")
w(f"Snapshot: `{m['generated_at']}` (rebuild with `python -m app.modules.nasa_hrp.build_snapshot`, see the end of this file).\n")
w("## Summary\n")
w("- The Resources tab was accessible. It lists **5 resources**: 3 NASA Human Research Program (HRP) pages and 2 Canadian Space Agency (CSA) articles.")
w("- **None of the 5 resources is a dataset**, and none links to one. " + m["datasets_note"].split(". ", 1)[1])
w(f"- Following the NASA resources one level down gives **{len(m['subpages'])} NASA pages** (5 hazard pages, 17 risk pages, research and study pages) "
  f"and **{len(m['documents'])} PDF documents** (evidence reports, NASA-STD-3001 technical briefs, research plans). All were downloaded and parsed.")
w(f"- From those documents the tool uses **{len(ev)} quantitative facts**. Each is stored with an exact quote; the build fails if a quote is not "
  "found in the source, and PDF facts carry the page number.")
w("- All 6 health indicators named in the challenge brief are supported (blood pressure, heart rate, blood sugar, body temperature, sleep hours, mood). "
  "Blood sugar and body temperature (and body mass) were added because of this review.")
w("- Because no resource contains wearable or self-report time series, the machine-learning models are still trained on **simulated** data. "
  "The resources are used where they genuinely apply: indicator choice, risk mapping, NASA's own prevention guidance, alert design, "
  "three published-number models, simulator calibration, and cited explanations.\n")

w("## 1. The five resources on the tab\n")
w("| # | Resource | Agency | Downloadable data? | Status | How the tool uses it |")
w("|---|---|---|---|---|---|")
for i, r in enumerate(m["resources"], 1):
    w(f"| {i} | [{r['title']}]({r['url']}) | {r['agency']} | No (information page) | {r['status']} | {USE[r['id']]} |")
w("")
w("Licensing: " + m["resources"][0]["license"] + " CSA: " + m["resources"][-1]["license"] + "\n")

w("## 2. What the resources link to\n")
w(f"### 2.1 NASA pages ({len(m['subpages'])}, all downloaded; text bundled in `data/challenge_snapshot/pages.json`)\n")
groups = {"Hazard pages": [], "Risk pages": [], "HRP element pages": [], "Study / research pages": []}
for s in m["subpages"]:
    slug = s["slug"]
    g = ("Hazard pages" if slug.startswith("hazard-") else "Risk pages" if slug.startswith("risk") else
         "HRP element pages" if slug in ("radiation", "human-health-countermeasures", "human-factors-and-behavioral-performance")
         else "Study / research pages")
    groups[g].append(f"[{s['title']}]({s['url']})")
for g, items in groups.items():
    w(f"- **{g} ({len(items)}):** " + "; ".join(items))
w("")
w("Study pages such as *Standard Measures*, *Artemis II Standard Measures*, *CIPHER*, *Omics Archive* and *Immune Biomarkers* describe "
  "exactly the kind of crew data this tool would want (wrist activity and light, sleep reports, saliva and blood markers, cognition and "
  "balance tests), but **they publish descriptions, not data**. That data lives in NASA's controlled-access archives and needs a formal "
  "data request. **It is not integrated.**\n")
w(f"### 2.2 Documents ({len(m['documents'])} PDFs, downloaded and text-extracted; cached locally in `data/challenge_cache/`, not committed)\n")
w("| Document | Pages | Size | SHA-256 (first 12) | Used for |")
w("|---|---|---|---|---|")
for d in m["documents"]:
    w(f"| [{d['file']}]({d['url']}) | {d.get('pages', '-')} | {d.get('bytes', 0) / 1e6:.1f} MB | `{d.get('sha256', '')[:12]}` | {DOC_USE.get(d['file'], '')} |")
w("")

w("## 3. Facts taken from the resources (verified quotes)\n")
w("| Fact used by the tool | Source | Exact quote checked |")
w("|---|---|---|")
for e in ev:
    src = f"[{e['source']}{', p. ' + str(e['page']) if e.get('page') else ''}]({e['source_url']}{'#page=' + str(e['page']) if e.get('page') else ''})"
    w(f"| {e['statement']} | {src} | \"{e['quote']}\" |")
w("")

w("## 4. Mapping to the tool's modules\n")
w("### 4.1 Indicators named in the challenge brief\n")
w("| Challenge indicator | Tool metric(s) | Collected by | What the resources say |")
w("|---|---|---|---|")
notes = {"blood pressure": "In-flight BP is lower than pre-flight (Cardio Evidence Report p.23) -> personal in-flight baseline; orthostatic intolerance is the main risk on return.",
         "heart rate": "In-flight HR lower than pre-flight (same source) -> personal baseline + anomaly model.",
         "blood sugar": "Glucose can stay normal while insulin rises ~50% (Cardio ER p.40) -> glucose shown with that caveat; range from NASA OSD-575 lab file.",
         "body temperature": "Core temperature ~1 °C higher in microgravity (Nutrition report p.21) -> compared with own in-flight baseline, not Earth fever cut-offs.",
         "daily sleep hours": "Sleep risk page: work overload, irregular light-dark cycles; 16 sunrises/day on ISS.",
         "mood": "Behavioral conditions risk page; isolation & confinement hazard."}
for ind, mets in CHALLENGE_INDICATORS.items():
    w(f"| {ind} | {', '.join('`' + x + '`' for x in mets)} | HealthKit / Health Connect / check-ins / simulator | {notes[ind]} |")
w("")
w("### 4.2 NASA HRP risks -> what the tool can monitor\n")
cat_of = {s: c for c, ss in RISK_CATEGORIES.items() for s in ss}
w("| Risk (NASA HRP page) | NASA category | Hazards (our mapping) | Coverage | Tool indicators | Facts |")
w("|---|---|---|---|---|---|")
for slug, mon in RISK_MONITORING.items():
    p = pages.get(slug, {})
    facts = ", ".join(e["id"] for e in ev if slug in e["risks"]) or "-"
    w(f"| [{p.get('title', slug)}]({p.get('url', '')}) | {cat_of.get(slug, '')} | {', '.join(mon['hazards'])} | {MON[mon['monitoring']]} | "
      f"{', '.join('`' + x + '`' for x in mon['metrics']) or '-'} | {facts} |")
w("")
w("NASA's Risks page groups risks into *Human Physiology*, *Behavioral Performance* and *Space Radiation*. It does not list which hazard "
  "causes which risk, so the hazard column is **our mapping**, based on the hazard pages' text.\n")

w("## 5. Prioritising NASA data for training and evaluation\n")
w("| Candidate | Downloadable? | Suitable for training? | Decision |")
w("|---|---|---|---|")
w("| Challenge resources (5 pages, 40 sub-pages, 12 PDFs) | Yes (text) | No: no per-person time series | Used for evidence, thresholds, guidance and simulator calibration |")
w("| Standard Measures / Artemis II Standard Measures / CIPHER / Omics Archive (described on the resource pages) | No (controlled access) | Would be ideal | Not integrated; data request needed |")
w("| NASA OSDR Inspiration4 lab panels OSD-569 / OSD-575 (NASA, outside the tab, integrated earlier) | Yes | No: 4 people, 6 time points, no wearables | Research context and the glucose reference range |")
w("")
w("Models are therefore designed around data that actually exists on consumer devices (resting HR, HRV, sleep, steps, check-ins), and are "
  "trained and evaluated on simulated data, labelled as such everywhere (see [AI_MODELS.md](AI_MODELS.md)). NASA facts are used to make the "
  "simulator more realistic: in-flight core temperature ~1 °C above Earth, body mass falling ~2.4% per 100 days.\n")

w("## 6. Scientific models and instruments reused (with attribution)\n")
w("| Method | Origin | Where in the tool | Status |")
w("|---|---|---|---|")
w("| Bone-loss projection, 1-1.5%/month | NASA Evidence Report *Risk of Bone Fracture* (p.4); HRP hazard page | `intelligence/risks.py` bone model | Implemented |")
w("| Body-mass change vs 2.4%/100 days | NASA *Human Adaptation to Spaceflight: The Role of Food and Nutrition* (p.22) | body-mass model + alert | Implemented |")
w("| Cumulative dose vs 30-120 mGy per 6-month ISS stay | NASA Cardiovascular Evidence Report (p.69) | radiation model | Implemented (estimate) |")
w("| Personal in-flight baselines for HR/BP/temperature | Cardio ER p.23; Nutrition report p.21 | alert rules, anomaly model | Implemented |")
w("| NASA-TLX workload index | Hart & Staveland, NASA Ames (1988) | questionnaires module | Implemented (raw TLX) |")
w("| Samn-Perelli fatigue checklist | Samn & Perelli, USAF (1982) | questionnaires module | Implemented |")
w("| Psychomotor vigilance-style reaction test | Dinges & Powell (1985) | questionnaires module | Implemented (simplified) |")
w("| HOMA-IR insulin resistance index | Matthews et al. (1985), cited in the Cardio ER | - | Not implemented: needs insulin, which consumer devices do not measure |")
w("| Isolation Forest | Liu, Ting & Zhou (2008) | anomaly model | Implemented |")
w("| Damped-trend exponential smoothing | Holt (1957); Gardner & McKenzie (1985) | forecast model | Implemented |")
w("")

w("## 7. Limitations\n")
w("- No dataset in the resources, so model accuracy figures are simulation results only.")
w("- Facts are population averages from other crews and missions. They are shown as context and reference ranges, never as an individual's value.")
w("- The hazard-to-risk mapping and the coverage levels are the team's judgement, not NASA's.")
w("- Alert thresholds not taken from a resource (for example 38.5 °C, glucose < 54 or >= 140 mg/dL, 5% body-mass loss) are demo values, labelled as such.")
w("- PDFs are not redistributed in the repository (size). The manifest records URL, size and SHA-256 so the exact files can be re-downloaded and checked.")
w("- CSA articles are Crown copyright: linked and used for one verified fact, not copied.")
w("- The two HRP Risk Approach Plan PDFs and the training/education PDFs contain no health measurements and are listed for completeness only.\n")

w("## 8. Reproduce\n")
w("```bash\ncd backend\nPYTHONPATH=..:. python -m app.modules.nasa_hrp.build_snapshot   # downloads, parses, verifies quotes; non-zero exit on any failure\ncd ..\npython scripts/write_challenge_doc.py                             # regenerates this file\n```")
w("Tests: `backend/tests/test_challenge.py` checks that all 5 resources are present, every fact is verified (PDF facts have pages), all "
  "challenge indicators are supported, and the risk view and vitals rules behave.")

(ROOT / "docs" / "NASA_CHALLENGE_RESOURCES.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("wrote docs/NASA_CHALLENGE_RESOURCES.md", len(L), "lines")
