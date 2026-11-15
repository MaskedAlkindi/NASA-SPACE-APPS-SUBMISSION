# Datasets

HEALTH-01 separates three classes of data everywhere, from the database to the UI badges to the assistant context:

| Class | Meaning | Where it comes from |
|---|---|---|
| `real` | Measurements of a real person | iOS HealthKit / Android Health Connect uploads (account `pilot`), manual check-ins |
| `research` | Published research data about *other* people | NASA OSDR (Inspiration4 crew) |
| `simulated` | Synthetic data | `ml/datasets/synthetic.py`: demo crew, mission simulator, model training |

## NASA sources investigated

| Source | URL | How it was used |
|---|---|---|
| NASA Open Science Data Repository (OSDR) | https://osdr.nasa.gov/ | **Integrated**: metadata, file listings, and data downloads |
| OSDR public API | https://www.nasa.gov/osdr-api/ | Endpoints `/osdr/data/search`, `/osdr/data/osd/meta/{n}`, `/osdr/data/osd/files/{n}`, `/geode-py/ws/studies/OSD-{n}/download` (no API key) |
| NASA Human Research Program | https://www.nasa.gov/hrp/ and https://humanresearchroadmap.nasa.gov/ | Curated, **paraphrased** risk summaries (sleep and circadian, cardiovascular, CO₂, radiation, behavioural health, exercise) with source links |
| NASA Life Sciences Portal | https://nlsp.nasa.gov/ | Reviewed; no bulk public API suitable for automated ingestion was found, so it is not integrated |
| api.nasa.gov | https://api.nasa.gov/ | Reviewed; its APIs (APOD, NeoWs, DONKI, …) contain no astronaut physiology, so it is not integrated. DONKI (space weather) is a candidate future source for real solar-particle-event context |

## Imported OSDR datasets (data downloaded and parsed)

| Accession | Content | Files | Rows parsed |
|---|---|---|---|
| **OSD-569** | SpaceX Inspiration4: whole-blood measurements, including **complete blood count (CBC)** | `LSDS-7_Complete_Blood_Count_CBC.upload_SUBMITTED.csv` | ~600 |
| **OSD-575** | SpaceX Inspiration4: **comprehensive metabolic panel** and **serum cardiovascular biomarker panel** | `LSDS-8_Comprehensive_Metabolic_Panel_CMP.upload_SUBMITTED.csv`, `LSDS-8_Multiplex_serum.cardiovascular.EvePanel_SUBMITTED.csv` | ~700 |

Together these give 1,314 observations: 4 crew (C001–C004), timepoints L-92, L-44, L-3 (pre-flight) and R+1, R+45, R+82 (post-flight). The mission was 3 days in low Earth orbit (16–18 Sep 2021).

- **Provenance recorded per dataset:** accession, title, description, organism, mission and dates, project type, assay types, release date, OSDR URL, DOI (10.1038/s41586-024-07639-y, Overbey et al., *Nature* 2024), citation, file list with sizes and restricted flags, download origin (network / cache / snapshot), and retrieval time.
- **Provenance recorded per observation:** source file, subject, analyte, value, unit, lab reference range, timepoint, and phase.
- **License:** NASA OSDR public data under NASA's open-science / open-data policy, with no access restrictions. Cite the accession and publication.
- **Parsing:** only numeric values present in the file are stored. Nothing is imputed, and rows without numeric values are counted and skipped.
- **Restricted / unavailable data:** files flagged `restricted` are skipped and reported. Network errors fall back from the runtime cache to the bundled snapshot to a reported error, and the app keeps running.
- **Caching:** runtime cache in the `nasa_cache` Docker volume. A bundled snapshot of the three CSVs plus metadata lives in `data/nasa_snapshot/` (see its `PROVENANCE.md`) so the demo works fully offline (`NASA_ONLINE=false`).

### Computed findings

For each analyte, HEALTH-01 computes the mean pre-flight value per crew member, the percent change at R+1, and how many crew changed in the same direction. A finding is marked *notable* when the mean change is at least 10% and at least 3 of the 4 crew agree. These are **descriptive statistics only** (n = 4, no significance testing) and are labelled that way in the UI and assistant. Examples from the current data: CRP was higher at R+1, absolute lymphocytes were lower, and glucose was higher.

## Discovered (metadata only)

The importer also runs OSDR searches (`Inspiration4`, `astronaut`, `human spaceflight`, `cardiovascular microgravity`, `sleep spaceflight`, `space radiation`) and stores metadata for about 60 further studies. Most are omics or model-organism studies. They can be browsed on the Research page but are not downloaded.

## Why NASA data does not train the wearable models

The public human OSDR data contains **no** heart rate, HRV, sleep, activity or questionnaire time series, and it covers only 4 people at 6 timepoints. That cannot train or validate a personalised wearable model. As the challenge brief allows, HEALTH-01 therefore:

1. uses NASA data for **scientific context and explanations** (Research page, alert context, assistant passages), and
2. uses **clearly labelled synthetic data** to train and demonstrate the ML pipeline (see [AI_MODELS.md](AI_MODELS.md)).

## Synthetic data

`ml/datasets/synthetic.py` holds a documented generative model:

- Each person has their own baselines (resting HR, HRV, sleep need, chronotype, steps, exercise, blood pressure, reaction time).
- Workload and sleep debt and irregular sleep timing affect resting HR, HRV, fatigue (Samn-Perelli 1–7), mood, stress and reaction time. The directions follow the literature; the coefficients are invented.
- Labelled scenario episodes can be injected: `sleep_disruption`, `fatigue_buildup`, `cardio_anomaly`, `illness_like`, `co2_scrubber_fault`, `radiation_event`.
- Environment values (CO₂ ~2–3 mmHg, dose rate ~18 µGy/h baseline) are illustrative, not mission telemetry.

The four demo crew members (ORION, VEGA, LYRA, ATLAS) and the mission are **fictional**.
