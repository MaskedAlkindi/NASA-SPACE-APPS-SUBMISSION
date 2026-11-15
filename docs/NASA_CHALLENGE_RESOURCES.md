# NASA challenge resources: what they contain and how the tool uses them

Challenge: *Create Health Monitoring Software for Astronauts on Space Missions* (NASA Space Apps 2026).  
Resources tab: <https://www.spaceappschallenge.org/2026/challenges/health-monitoring-software/?tab=resources>  
Snapshot: `2026-11-14T13:21:41+00:00` (rebuild with `python -m app.modules.nasa_hrp.build_snapshot`, see the end of this file).

## Summary

- The Resources tab was accessible. It lists **5 resources**: 3 NASA Human Research Program (HRP) pages and 2 Canadian Space Agency (CSA) articles.
- **None of the 5 resources is a dataset**, and none links to one. Studies described there (e.g. Spaceflight Standard Measures, CIPHER, Omics Archive) keep crew data in controlled-access archives that require a formal data request.
- Following the NASA resources one level down gives **40 NASA pages** (5 hazard pages, 17 risk pages, research and study pages) and **12 PDF documents** (evidence reports, NASA-STD-3001 technical briefs, research plans). All were downloaded and parsed.
- From those documents the tool uses **14 quantitative facts**. Each is stored with an exact quote; the build fails if a quote is not found in the source, and PDF facts carry the page number.
- All 6 health indicators named in the challenge brief are supported (blood pressure, heart rate, blood sugar, body temperature, sleep hours, mood). Blood sugar and body temperature (and body mass) were added because of this review.
- Because no resource contains wearable or self-report time series, the machine-learning models are still trained on **simulated** data. The resources are used where they genuinely apply: indicator choice, risk mapping, NASA's own prevention guidance, alert design, three published-number models, simulator calibration, and cited explanations.

## 1. The five resources on the tab

| # | Resource | Agency | Downloadable data? | Status | How the tool uses it |
|---|---|---|---|---|---|
| 1 | [5 Hazards of Human Spaceflight](https://www.nasa.gov/hrp/hazards/) | NASA | No (information page) | downloaded | The five hazards (shown on the Hazards & Risks page; hazard text used by the assistant). |
| 2 | [Risks of Human Spaceflight](https://www.nasa.gov/hrp/risks/) | NASA | No (information page) | downloaded | The 17 HRP risks: risk text, NASA's "What can be done about it?" guidance, links to evidence reports. |
| 3 | [Ongoing HRP Research in Space](https://www.nasa.gov/hrp/ongoing-hrp-research/) | NASA | No (information page) | downloaded | Descriptions of ongoing studies (Standard Measures, CIPHER, Omics Archive, Immune Biomarkers...) used to choose indicators; links to NASA-STD-3001 technical briefs. |
| 4 | [Monitoring Radiation for Astronaut Health](https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp) | CSA | No (information page) | downloaded | Radiation context: neutrons are ~30% of ISS radiation (verified fact). |
| 5 | [Why Do We Conduct Science Experiments in Space?](https://www.asc-csa.gc.ca/eng/iss/science/why-do-we-conduct-science-experiments-in-space.asp) | CSA | No (information page) | downloaded | Context only (why ISS research matters; risks of longer missions). No measurements. |

Licensing: NASA content is generally not subject to copyright in the United States (NASA media usage guidelines). Cite NASA as the source. CSA: Government of Canada (CSA) content - Crown copyright. Linked and summarised only; the full text is not redistributed.

## 2. What the resources link to

### 2.1 NASA pages (40, all downloaded; text bundled in `data/challenge_snapshot/pages.json`)

- **Hazard pages (5):** [Hazard: Distance From Earth](https://www.nasa.gov/hrp/hazard-distance-from-earth/); [Hazard: Gravity Fields](https://www.nasa.gov/hrp/hazard-gravity-fields/); [Hazard: Hostile/Closed Environments](https://www.nasa.gov/hrp/hazard-hostile-closed-environments/); [Hazard: Isolation and Confinement](https://www.nasa.gov/hrp/hazard-isolation-and-confinement/); [Hazard: Space Radiation](https://www.nasa.gov/hrp/hazard-space-radiation/)
- **Risk pages (17):** [Risk from Inadequate Sleep and Irregular Schedules](https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/); [Risk of Altered Immune System Responses](https://www.nasa.gov/reference/risk-of-altered-immune-system-responses/); [Risk of Altered Sensorimotor and Vestibular Function](https://www.nasa.gov/reference/risk-of-altered-sensorimotor-and-vestibular-function/); [Risk of behavioral changes and psychiatric disorders](https://www.nasa.gov/reference/risk-of-behavioral-conditions-and-psychiatric-disorders/); [Risk of Cardiovascular Adaptations](https://www.nasa.gov/reference/risk-of-cardiovascular-adaptations/); [Risk of Decompression Sickness](https://www.nasa.gov/reference/risk-of-decompression-sickness/); [Risk of Host-Microorganism Interactions](https://www.nasa.gov/reference/risk-of-host-microorganism-interactions/); [Risk of Hypoxia](https://www.nasa.gov/reference/risk-of-hypoxia/); [Risk of Inadequate Food and Nutrition](https://www.nasa.gov/reference/risk-of-inadequate-food-and-nutrition/); [Risk of inadequate systems operations support](https://www.nasa.gov/reference/risk-of-inadequate-systems-operations-support/); [Risk of inadequate teamwork](https://www.nasa.gov/reference/risk-of-inadequate-teamwork/); [Risk of Injury and Compromised Performance from Spacewalks](https://www.nasa.gov/reference/risk-of-injury-and-compromised-performance-from-extravehicular-activity-eva/); [Risk of injury from dynamic loads](https://www.nasa.gov/reference/risk-of-injury-from-dynamic-loads/); [Risk of radiation-induced cancers](https://www.nasa.gov/reference/risk-of-radiation-induced-cancers/); [Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness](https://www.nasa.gov/reference/risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness/); [Risk of Spaceflight Associated Neuro-ocular Syndrome (SANS)](https://www.nasa.gov/reference/risk-of-spaceflight-associated-neuro-ocular-syndrome-sans/); [Risk of Spaceflight-Induced Bone Changes](https://www.nasa.gov/reference/risk-of-spaceflight-induced-bone-changes/)
- **HRP element pages (3):** [Human Factors and Behavioral Performance](https://www.nasa.gov/hrp/human-factors-and-behavioral-performance/); [Human Health Countermeasures](https://www.nasa.gov/hrp/human-health-countermeasures/); [Space Radiation](https://www.nasa.gov/hrp/radiation/)
- **Study / research pages (15):** [ARCHeR](https://www.nasa.gov/reference/archer/); [Artemis II Standard Measures](https://www.nasa.gov/reference/artemis-ii-standard-measures/); [B-Complex](https://www.nasa.gov/reference/b-complex/); [Brain Fluid Pressure](https://www.nasa.gov/reference/brain-fluid-pressure/); [CIPHER](https://www.nasa.gov/reference/cipher/); [Immune Biomarkers](https://www.nasa.gov/reference/immune-biomarkers/); [Omics archive](https://www.nasa.gov/reference/omics-archive/); [Simulating Manual Piloting for Moon Landings](https://www.nasa.gov/reference/simulating-manual-piloting-for-moon-landings/); [Spacecraft Occupant Protection](https://www.nasa.gov/reference/spacecraft-occupant-protection/); [Spinal Fluid Biomarkers](https://www.nasa.gov/reference/spinal-fluid-biomarkers/); [Standard Measures](https://www.nasa.gov/reference/standard-measures/); [Tempus Pro](https://www.nasa.gov/reference/tempus-pro/); [Thigh Cuff](https://www.nasa.gov/reference/thigh-cuff/); [Venous Haemostasis](https://www.nasa.gov/reference/venous-haemostasis/); [Zero T2](https://www.nasa.gov/reference/zero-t2/)

Study pages such as *Standard Measures*, *Artemis II Standard Measures*, *CIPHER*, *Omics Archive* and *Immune Biomarkers* describe exactly the kind of crew data this tool would want (wrist activity and light, sleep reports, saliva and blood markers, cognition and balance tests), but **they publish descriptions, not data**. That data lives in NASA's controlled-access archives and needs a formal data request. **It is not integrated.**

### 2.2 Documents (12 PDFs, downloaded and text-extracted; cached locally in `data/challenge_cache/`, not committed)

| Document | Pages | Size | SHA-256 (first 12) | Used for |
|---|---|---|---|---|
| [Nutrition_ER_human_adaptation_2020_final.pdf](https://humanresearchroadmap.nasa.gov/Evidence/other/Nutrition%20ER_human_adaptation_2020_final.pdf) | 135 | 8.4 MB | `b339f6f88200` | Core temperature +1 °C, body mass -2.4%/100 d, blood volume, urine calcium -> temperature rule design, body-mass model, simulator calibration. |
| [Fracture.pdf](https://humanresearchroadmap.nasa.gov/Evidence/reports/Fracture.pdf) | 34 | 0.8 MB | `6b1191a6e258` | Bone-loss rate 1-1.5%/month -> bone projection model. |
| [Cardio_Risk_EB_2022_FINAL_4-3-2023.pdf](https://humanresearchroadmap.nasa.gov/evidence/reports/Cardio%20Risk%20EB%202022%20FINAL_4-3-2023.pdf) | 161 | 2.1 MB | `70e4cd0e5902` | In-flight HR/BP lower than pre-flight, orthostatic intolerance, insulin resistance, ISS/Mars dose ranges -> personal in-flight baselines, glucose caveat, radiation model. |
| [Degen.pdf](https://humanresearchroadmap.nasa.gov/evidence/reports/Degen.pdf) | 52 | 1.3 MB | `e59e434585a4` | Radiation and cardiovascular/degenerative risk background. No fact extracted yet. |
| [160410main_space_training_fact_sheet.pdf](https://www.nasa.gov/wp-content/uploads/2015/10/160410main_space_training_fact_sheet.pdf) | 2 | 0.2 MB | `dcf2571e772c` | Astronaut training fact sheet. Not health data; not used. |
| [whatisyourspaceheight.pdf](https://www.nasa.gov/wp-content/uploads/2018/05/whatisyourspaceheight.pdf) | 7 | 5.9 MB | `6b6889df21b0` | Educational activity (spine lengthening in space). Not used. |
| [ochmo-tb-030-bone-loss.pdf](https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-030-bone-loss.pdf) | 26 | 1.6 MB | `3b86e09f0e47` | Vitamin D optimal range (NASA-STD-3001 brief) -> bone risk evidence. |
| [ochmo-mtb-007-venous-thrombosis-in-spaceflight.pdf](https://www.nasa.gov/wp-content/uploads/2026/01/ochmo-mtb-007-venous-thrombosis-in-spaceflight.pdf) | 18 | 1.5 MB | `d68f5c57ad22` | Venous thrombosis background (needs ultrasound; not monitorable by the tool). |
| [hrp-rap-for-web-62026.pdf](https://www.nasa.gov/wp-content/uploads/2026/06/hrp-rap-for-web-62026.pdf) | 14 | 1.2 MB | `d4e77d646fa6` | HRP Risk Approach Plans (research planning charts). Not measurement data. |
| [hrp-rap-for-web-62026-hfbp.pdf](https://www.nasa.gov/wp-content/uploads/2026/08/hrp-rap-for-web-62026-hfbp.pdf) | 6 | 0.9 MB | `3a1f03181925` | Risk Approach Plans, Human Factors & Behavioral Performance. Planning only. |
| [hrp-rap-for-web-62026-hhc.pdf](https://www.nasa.gov/wp-content/uploads/2026/08/hrp-rap-for-web-62026-hhc.pdf) | 9 | 1.2 MB | `ce4b826ec112` | Risk Approach Plans, Human Health Countermeasures. Planning only. |
| [hrp-rap-for-web-62026-sr.pdf](https://www.nasa.gov/wp-content/uploads/2026/08/hrp-rap-for-web-62026-sr.pdf) | 3 | 0.8 MB | `b0b54c5028e3` | Risk Approach Plans, Space Radiation. Planning only. |

## 3. Facts taken from the resources (verified quotes)

| Fact used by the tool | Source | Exact quote checked |
|---|---|---|
| Weight-bearing bones lose on average 1-1.5% of mineral density per month in spaceflight. | [Fracture.pdf, p. 4](https://humanresearchroadmap.nasa.gov/Evidence/reports/Fracture.pdf#page=4) | "averaged loss rates between 1-1.5% per month for normally weight-bearing skeletal sites" |
| NASA HRP: bones lose on average 1% to 1.5% of mineral density per month during spaceflight. | [hazard-gravity-fields](https://www.nasa.gov/hrp/hazard-gravity-fields/) | "weight-bearing bones lose on average 1% to 1.5% of mineral density per month during spaceflight" |
| Core body temperature rose by about 1 °C at rest in microgravity on the ISS, so fever cut-offs set on Earth are unreliable; the tool compares temperature with each astronaut's own in-flight baseline. | [Nutrition_ER_human_adaptation_2020_final.pdf, p. 21](https://humanresearchroadmap.nasa.gov/Evidence/other/Nutrition%20ER_human_adaptation_2020_final.pdf#page=21) | "core body temperature was shown to increase by about 1" |
| Across spaceflight data, body weight fell by about 2.4% per 100 days on average. | [Nutrition_ER_human_adaptation_2020_final.pdf, p. 22](https://humanresearchroadmap.nasa.gov/Evidence/other/Nutrition%20ER_human_adaptation_2020_final.pdf#page=22) | "average loss of 2.4% of body weight per 100 days" |
| Losses of more than 10% of pre-flight body mass were recorded on Mir. | [Nutrition_ER_human_adaptation_2020_final.pdf, p. 22](https://humanresearchroadmap.nasa.gov/Evidence/other/Nutrition%20ER_human_adaptation_2020_final.pdf#page=22) | "Body mass losses of more than 10% of preflight body mass were recorded on Mir" |
| Blood volume falls by 10-15% in flight and takes about 2 weeks to stabilise. | [Nutrition_ER_human_adaptation_2020_final.pdf, p. 8](https://humanresearchroadmap.nasa.gov/Evidence/other/Nutrition%20ER_human_adaptation_2020_final.pdf#page=8) | "10% to 15% reduction in blood volume that takes about 2 weeks to stabilize" |
| In flight, 24-hour urine volume was about 17% lower and urinary calcium concentration 50% higher, raising kidney-stone risk; fluid intake matters. | [Nutrition_ER_human_adaptation_2020_final.pdf, p. 38](https://humanresearchroadmap.nasa.gov/Evidence/other/Nutrition%20ER_human_adaptation_2020_final.pdf#page=38) | "Twenty-four-hour urine volume is about 17% lower and urinary calcium concentration is 50% greater during flight than before flight" |
| In-flight heart rate and systolic and diastolic blood pressure were lower than pre-flight values, so Earth norms do not fit; the tool uses in-flight personal baselines. | [Cardio_Risk_EB_2022_FINAL_4-3-2023.pdf, p. 23](https://humanresearchroadmap.nasa.gov/evidence/reports/Cardio%20Risk%20EB%202022%20FINAL_4-3-2023.pdf#page=23) | "Inflight heart rate and systolic and diastolic blood pressure were decreased when compared to the preflight values" |
| Orthostatic intolerance (light-headedness on standing) is the primary cardiovascular risk when returning to gravity. | [Cardio_Risk_EB_2022_FINAL_4-3-2023.pdf, p. 8](https://humanresearchroadmap.nasa.gov/evidence/reports/Cardio%20Risk%20EB%202022%20FINAL_4-3-2023.pdf#page=8) | "is considered the primary risk during re-exposure to acceleration" |
| After long flights blood glucose was unchanged, but insulin was about 50% higher and HOMA-IR about 60% higher, a sign of insulin resistance. Glucose alone can look normal. | [Cardio_Risk_EB_2022_FINAL_4-3-2023.pdf, p. 40](https://humanresearchroadmap.nasa.gov/evidence/reports/Cardio%20Risk%20EB%202022%20FINAL_4-3-2023.pdf#page=40) | "blood glucose levels were not different after long -duration spaceflight but circulating insulin was increased by ~50%" |
| Absorbed dose for a six-month ISS stay is about 30-120 mGy; a Mars mission is expected to be 175-450 mGy. | [Cardio_Risk_EB_2022_FINAL_4-3-2023.pdf, p. 69](https://humanresearchroadmap.nasa.gov/evidence/reports/Cardio%20Risk%20EB%202022%20FINAL_4-3-2023.pdf#page=69) | "30-120 mGy for six-month stays" |
| NASA-STD-3001 bone-loss brief: optimal 25-OH vitamin D range is 35-90 ng/mL. | [ochmo-tb-030-bone-loss.pdf, p. 16](https://www.nasa.gov/wp-content/uploads/2023/12/ochmo-tb-030-bone-loss.pdf#page=16) | "The optimal/desired range for 25-OH Vitamin D is 35-90 ng/ml" |
| ISS crews see 16 sunrises and sunsets a day, which can disrupt the sleep-wake cycle. | [risk-from-inadequate-sleep-and-irregular-schedules](https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/) | "Astronauts witness 16 sunrises and sunsets per day aboard the space station" |
| CSA: neutrons make up about 30% of total radiation on the ISS and need dedicated measurement. | [csa-radiation](https://www.asc-csa.gc.ca/eng/news/articles/2026/2026-02-26-monitoring-radiation-astronaut-health.asp) | "contributes to about 30% of total radiation on the ISS" |

## 4. Mapping to the tool's modules

### 4.1 Indicators named in the challenge brief

| Challenge indicator | Tool metric(s) | Collected by | What the resources say |
|---|---|---|---|
| blood pressure | `blood_pressure_systolic`, `blood_pressure_diastolic` | HealthKit / Health Connect / check-ins / simulator | In-flight BP is lower than pre-flight (Cardio Evidence Report p.23) -> personal in-flight baseline; orthostatic intolerance is the main risk on return. |
| heart rate | `heart_rate`, `resting_heart_rate` | HealthKit / Health Connect / check-ins / simulator | In-flight HR lower than pre-flight (same source) -> personal baseline + anomaly model. |
| blood sugar | `blood_glucose` | HealthKit / Health Connect / check-ins / simulator | Glucose can stay normal while insulin rises ~50% (Cardio ER p.40) -> glucose shown with that caveat; range from NASA OSD-575 lab file. |
| body temperature | `body_temperature` | HealthKit / Health Connect / check-ins / simulator | Core temperature ~1 °C higher in microgravity (Nutrition report p.21) -> compared with own in-flight baseline, not Earth fever cut-offs. |
| daily sleep hours | `sleep_duration` | HealthKit / Health Connect / check-ins / simulator | Sleep risk page: work overload, irregular light-dark cycles; 16 sunrises/day on ISS. |
| mood | `mood_score` | HealthKit / Health Connect / check-ins / simulator | Behavioral conditions risk page; isolation & confinement hazard. |

### 4.2 NASA HRP risks -> what the tool can monitor

| Risk (NASA HRP page) | NASA category | Hazards (our mapping) | Coverage | Tool indicators | Facts |
|---|---|---|---|---|---|
| [Risk of Cardiovascular Adaptations](https://www.nasa.gov/reference/risk-of-cardiovascular-adaptations/) | Risks Involving Human Physiology | Gravity Fields, Space Radiation | Measured | `resting_heart_rate`, `hrv_sdnn`, `blood_pressure_systolic`, `blood_pressure_diastolic`, `oxygen_saturation` | blood-volume, inflight-hr-bp, orthostatic, insulin-resistance |
| [Risk from Inadequate Sleep and Irregular Schedules](https://www.nasa.gov/reference/risk-from-inadequate-sleep-and-irregular-schedules/) | Risks Involving Behavioral Performance | Isolation and Confinement | Measured | `sleep_duration`, `sleep_midpoint`, `sleep_efficiency`, `fatigue_score`, `workload_tlx` | sunrises |
| [Risk of behavioral changes and psychiatric disorders](https://www.nasa.gov/reference/risk-of-behavioral-conditions-and-psychiatric-disorders/) | Risks Involving Behavioral Performance | Isolation and Confinement, Distance from Earth | Measured | `mood_score`, `stress_score`, `reaction_time` | - |
| [Risk of Reduced Cardiorespiratory and Musculoskeletal Fitness](https://www.nasa.gov/reference/risk-of-reduced-cardiorespiratory-and-musculoskeletal-fitness/) | Risks Involving Human Physiology | Gravity Fields | Measured | `exercise_minutes`, `steps`, `resting_heart_rate` | - |
| [Risk of Spaceflight-Induced Bone Changes](https://www.nasa.gov/reference/risk-of-spaceflight-induced-bone-changes/) | Risks Involving Human Physiology | Gravity Fields | Partly (related indicators / model) | `exercise_minutes` | bone-loss-rate, bone-loss-rate-web, urine-calcium, vitamin-d |
| [Risk of Inadequate Food and Nutrition](https://www.nasa.gov/reference/risk-of-inadequate-food-and-nutrition/) | Risks Involving Human Physiology | Distance from Earth | Food log (example marks, not a menu) | meal log, `body_mass`, `blood_glucose` | body-mass-loss, body-mass-mir, urine-calcium, insulin-resistance |
| [Risk of Altered Immune System Responses](https://www.nasa.gov/reference/risk-of-altered-immune-system-responses/) | Risks Involving Human Physiology | Hostile/Closed Environments, Space Radiation | Partly (related indicators / model) | `body_temperature` | core-temperature |
| [Risk of Host-Microorganism Interactions](https://www.nasa.gov/reference/risk-of-host-microorganism-interactions/) | Risks Involving Human Physiology | Hostile/Closed Environments | Partly (related indicators / model) | `body_temperature`, `cabin_humidity` | - |
| [Risk of radiation-induced cancers](https://www.nasa.gov/reference/risk-of-radiation-induced-cancers/) | Risks Involving Space Radiation | Space Radiation | Partly (related indicators / model) | `radiation_dose_rate` | radiation-dose-iss, neutron-share |
| [Risk of Hypoxia](https://www.nasa.gov/reference/risk-of-hypoxia/) | Risks Involving Human Physiology | Hostile/Closed Environments | Partly (related indicators / model) | `oxygen_saturation`, `cabin_pressure` | - |
| [Risk of Altered Sensorimotor and Vestibular Function](https://www.nasa.gov/reference/risk-of-altered-sensorimotor-and-vestibular-function/) | Risks Involving Human Physiology | Gravity Fields | Partly (related indicators / model) | `reaction_time` | - |
| [Risk of Spaceflight Associated Neuro-ocular Syndrome (SANS)](https://www.nasa.gov/reference/risk-of-spaceflight-associated-neuro-ocular-syndrome-sans/) | Risks Involving Human Physiology | Gravity Fields | Needs clinical exam | - | - |
| [Risk of Decompression Sickness](https://www.nasa.gov/reference/risk-of-decompression-sickness/) | Risks Involving Human Physiology | Hostile/Closed Environments | Not monitored (operational) | `cabin_pressure` | - |
| [Risk of Injury and Compromised Performance from Spacewalks](https://www.nasa.gov/reference/risk-of-injury-and-compromised-performance-from-extravehicular-activity-eva/) | Risks Involving Human Physiology | Hostile/Closed Environments, Gravity Fields | Not monitored (operational) | - | - |
| [Risk of injury from dynamic loads](https://www.nasa.gov/reference/risk-of-injury-from-dynamic-loads/) | Risks Involving Human Physiology | Gravity Fields | Not monitored (operational) | - | - |
| [Risk of inadequate systems operations support](https://www.nasa.gov/reference/risk-of-inadequate-systems-operations-support/) | Risks Involving Behavioral Performance | Distance from Earth | Not monitored (operational) | `workload_tlx` | - |
| [Risk of inadequate teamwork](https://www.nasa.gov/reference/risk-of-inadequate-teamwork/) | Risks Involving Behavioral Performance | Isolation and Confinement | Not monitored (operational) | `stress_score` | - |

NASA's Risks page groups risks into *Human Physiology*, *Behavioral Performance* and *Space Radiation*. It does not list which hazard causes which risk, so the hazard column is **our mapping**, based on the hazard pages' text.

## 5. Prioritising NASA data for training and evaluation

| Candidate | Downloadable? | Suitable for training? | Decision |
|---|---|---|---|
| Challenge resources (5 pages, 40 sub-pages, 12 PDFs) | Yes (text) | No: no per-person time series | Used for evidence, thresholds, guidance and simulator calibration |
| Standard Measures / Artemis II Standard Measures / CIPHER / Omics Archive (described on the resource pages) | No (controlled access) | Would be ideal | Not integrated; data request needed |
| NASA OSDR Inspiration4 lab panels OSD-569 / OSD-575 (NASA, outside the tab, integrated earlier) | Yes | No: 4 people, 6 time points, no wearables | Research context and the glucose reference range |

Models are therefore designed around data that actually exists on consumer devices (resting HR, HRV, sleep, steps, check-ins), and are trained and evaluated on simulated data, labelled as such everywhere (see [AI_MODELS.md](AI_MODELS.md)). NASA facts are used to make the simulator more realistic: in-flight core temperature ~1 °C above Earth, body mass falling ~2.4% per 100 days.

## 6. Scientific models and instruments reused (with attribution)

| Method | Origin | Where in the tool | Status |
|---|---|---|---|
| Bone-loss projection, 1-1.5%/month | NASA Evidence Report *Risk of Bone Fracture* (p.4); HRP hazard page | `intelligence/risks.py` bone model | Implemented |
| Body-mass change vs 2.4%/100 days | NASA *Human Adaptation to Spaceflight: The Role of Food and Nutrition* (p.22) | body-mass model + alert | Implemented |
| Cumulative dose vs 30-120 mGy per 6-month ISS stay | NASA Cardiovascular Evidence Report (p.69) | radiation model | Implemented (estimate) |
| Personal in-flight baselines for HR/BP/temperature | Cardio ER p.23; Nutrition report p.21 | alert rules, anomaly model | Implemented |
| NASA-TLX workload index | Hart & Staveland, NASA Ames (1988) | questionnaires module | Implemented (raw TLX) |
| Samn-Perelli fatigue checklist | Samn & Perelli, USAF (1982) | questionnaires module | Implemented |
| Psychomotor vigilance-style reaction test | Dinges & Powell (1985) | questionnaires module | Implemented (simplified) |
| HOMA-IR insulin resistance index | Matthews et al. (1985), cited in the Cardio ER | - | Not implemented: needs insulin, which consumer devices do not measure |
| Isolation Forest | Liu, Ting & Zhou (2008) | anomaly model | Implemented |
| Damped-trend exponential smoothing | Holt (1957); Gardner & McKenzie (1985) | forecast model | Implemented |

## 7. Limitations

- No dataset in the resources, so model accuracy figures are simulation results only.
- Facts are population averages from other crews and missions. They are shown as context and reference ranges, never as an individual's value.
- The hazard-to-risk mapping and the coverage levels are the team's judgement, not NASA's.
- Alert thresholds not taken from a resource (for example 38.5 °C, glucose < 54 or >= 140 mg/dL, 5% body-mass loss) are demo values, labelled as such.
- PDFs are not redistributed in the repository (size). The manifest records URL, size and SHA-256 so the exact files can be re-downloaded and checked.
- CSA articles are Crown copyright: linked and used for one verified fact, not copied.
- The two HRP Risk Approach Plan PDFs and the training/education PDFs contain no health measurements and are listed for completeness only.

## 8. Reproduce

```bash
cd backend
PYTHONPATH=..:. python -m app.modules.nasa_hrp.build_snapshot   # downloads, parses, verifies quotes; non-zero exit on any failure
cd ..
python scripts/write_challenge_doc.py                             # regenerates this file
```
Tests: `backend/tests/test_challenge.py` checks that all 5 resources are present, every fact is verified (PDF facts have pages), all challenge indicators are supported, and the risk view and vitals rules behave.
