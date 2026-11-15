# Dataset inventory and licensing (AI engine)

All datasets were downloaded from their official sources on 2026-11-14 and verified by inspecting files and labels.
Raw data is **not** redistributed in this repository (`data/external/` is git-ignored); provenance files record exactly
what was used.

| Dataset | Official source | Verified download | Licence (as checked) | Population | Used for | Status |
|---|---|---|---|---|---|---|
| PMData | https://datasets.simula.no/pmdata → https://osf.io/vx4bk | Yes, 16 people; daily files only (minute-level HR skipped) | **Conflict:** Simula page says CC BY 4.0, OSF `license.txt` says **CC BY-NC 4.0**. The stricter non-commercial terms are applied. Cite doi:10.1145/3339825.3394926 | 16 healthy adults, Norway, Fitbit Versa 2 | Train and evaluate `fatigue_pmdata` | Integrated |
| Stanford COVID-19 wearables (Mishra et al. 2020) | Data link in medRxiv 10.1101/2020.07.06.20147512; labels in Nature BME Supplementary Data | Yes, 118 people HR/steps (sleep for 32); labels for 32 COVID-19 + 32 other illness events | No explicit licence; public research release. **Evaluation only, not redistributed**; code in the authors' LAAD repo is MIT | Smartwatch users, USA | Evaluate `illness_rhr` and the legacy anomaly model | Integrated (evaluation) |
| CGMacros v1.0.0 | https://physionet.org/content/cgmacros/1.0.0/ | Yes, 45 people (food photos skipped) | CC BY-NC-SA 4.0 | 45 adults: 15 normal, 16 prediabetes, 14 type 2 diabetes (by HbA1c) | Train and evaluate `glucose_metabolic` | Integrated |
| MMASH v1.0.0 | https://physionet.org/content/mmash/1.0.0/ | Yes, 22 people; `MMASH.zip` checksum verified against PhysioNet SHA256SUMS | ODbL v1.0 | 22 healthy young men, 24 h | Verify HR/HRV/sleep processing (`sleep_hrv`) | Integrated (verification) |
| CVES v1.0.0, sit-to-stand subset | https://physionet.org/content/cves/1.0.0/ (full set 174 GB; only `data/sit-stand/` + `subjects.csv` downloaded, 349 MB) | Yes, 71 recordings (ECG + arterial BP at 500 Hz) | ODC-By v1.0 | Older adults with/without stroke, hypertension, diabetes | Prototype `orthostatic` features | Research prototype |

## Data notes discovered during inspection

- **PMData scales run 1 = worst to 5 = best.** Fatigue correlates +0.40 with readiness, so "fatigue 2" means *more tired* than normal. The app's Samn-Perelli scale runs the other way, so the two are never mixed.
- **CGMacros HbA1c:** the data dictionary says mmol/mol, but the values (4.6–8.5) are percentages, so they are treated as %. Fasting insulin is in µU/mL, so HOMA-IR = glucose [mg/dL] × insulin / 405.
- **CVES sign convention:** the published "SBP change sit-2-stand" is **sit minus stand** (r = 0.993 with the study's own segment means). Our features use stand minus sit, and comparisons are sign-aligned.
- **Stanford dates** are shifted by the authors to protect privacy, consistently between data and labels.

## Not usable without approval (not integrated)

These have no public download. They need a NASA data request or approved-researcher access:
- NASA HERA analog data
- Spaceflight Standard Measures
- Inspiration4 smartwatch data
- Axiom / Polaris Dawn biobank
- LifeSnaps (restricted on Zenodo)
