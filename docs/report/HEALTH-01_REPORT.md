# HEALTH-01: system report

**Team Amerat 01 · NASA Space Apps Challenge 2026 · research prototype, not a medical device**

HEALTH-01 tracks astronaut health. Phones and wearables collect data, the server compares each person with their *own*
baseline, plug-in AI models and an assistant explain changes with their evidence, and everything links back to NASA's
human-research resources. This report lists what is implemented, what was measured, and what is not done yet.

---

## 1. What exists (by part)

### 1.1 Core platform (first build)

| Part | What it does |
|---|---|
| **Backend** (FastAPI, PostgreSQL, Docker Compose) | One measurement schema for every source; each value carries timestamp, device, source module, quality and data class (real / research / simulated). Upserts are idempotent. |
| **Plug-in modules** | Apple Health, Health Connect, cabin environment, questionnaires (Samn-Perelli fatigue, NASA-TLX, mood), mission simulator, NASA OSDR, exercise |
| **Personal baselines and alerts** | Rule-based alerts. Each alert carries its evidence (value, baseline, z-score), a recommendation and the related NASA risk. |
| **Original ML models** | Isolation-forest anomaly, fatigue estimate and 7-day forecast. Trained on simulated data and labelled that way. |
| **Assistant** | Switchable: OpenAI, a local Ollama model, or an offline explainer. Answers are grounded in the astronaut's data and the NASA findings, with a grounding check. |
| **NASA resources** | Every resource on the challenge Resources tab was read and inventoried (`docs/NASA_CHALLENGE_RESOURCES.md`). 14 numeric statements were checked word-for-word against the NASA PDFs, with page numbers. The Inspiration4 crew blood panels (OSD-569/575) were downloaded and analysed. |
| **Roles and privacy** | Astronaut, flight surgeon, mission control. Astronauts see only their own data, and requests for another astronaut return 404. Sign-in uses signed tokens. |

### 1.2 Plug-in AI engine with real-data models
Details: `docs/ai/`

| Part | What it does |
|---|---|
| **Model registry** | Every model is a folder with `manifest.json` and a Python class: inputs with units, datasets, licence, evidence level, alert policy. Models load lazily, run in isolation with timeouts, and can be switched on or off in the UI. Adding a model needs no core changes. |
| **Health data layer** | Per-astronaut view. Inputs are checked for missing, stale or wrong-unit data, and nothing is filled in with invented values. |
| **Alerts** | Concern-level results become alerts with evidence and an "evidence note", de-duplicated. Weaker results stay as insights. |
| **Exercise contracts** | `exercise_guidance.v1` and `exercise_session_summary.v1`, with JSON Schemas in `contracts/` |

Models trained or evaluated on real Earth-based research data. These are actual measured numbers; none of these models has been validated on astronauts.

| Model | Data | Result |
|---|---|---|
| **Illness signal** (resting heart rate) | Stanford wearable illness study, 117 people | Held-out half: 79% of 24 illness events caught, day specificity 95.8%, about 1 false alert per 30 healthy days, median alert 1 day before symptoms. The tuning half caught only 47%, so the estimate is uncertain. |
| **Glucose / metabolic** | CGMacros, 45 people | CGM insulin-resistance flag AUC 0.83 (95% CI 0.68–0.95). Post-meal rise error 18.6 mg/dL, against 26.6 mg/dL from carbs alone. |
| **Sleep and HRV** | MMASH, 22 people | Heart rate from beat timings within 1.1 bpm of the device (r 0.99); sleep-efficiency formula exact |
| **Fatigue** | PMData, 16 people | Weak: AUC 0.55 from wearables. Yesterday's self-report alone scores 0.62 to 0.68, so the model asks for a check-in. |
| **Orthostatic** | CVES, 71 recordings | Only moderate agreement with the published values (r ≈ 0.5), so it is **switched off** |

### 1.3 Exercise and fitness module
Built by our teammate's AI coding tool (Cursor) in parallel; Claude integrated and polished it.

| Part | What it does |
|---|---|
| **Programs** | Exercise catalog, example programs (general crew, personalised, mission phase), goals (day, week, month, year), calendar, manual log, adherence alerts |
| **Rep counting in the browser** | Squats, lunges and arm raises with pose landmarks. Video stays on the device; only counts are saved. Optional desktop pose service: `services/pose_inference/` |
| **Recommendations** | Rules-based, with a plug-in point for a model (`EXERCISE_RECOMMENDER_URL`). Health flags force human review. |
| **Integration** | Workouts flow into `exercise_minutes`, so the dashboards and AI models see them. The AI engine reads workout sessions read-only. |
| **Redesign for astronauts** (this round) | A **Today** view with a readiness check from the AI engine ("Go for training", "Train lighter today", "Rest and re-check", "Not enough data"), progress rings, streak, today's plan with cues, big start buttons, and a simpler set of tabs |

### 1.4 This round: product, connectivity, apps, LLM, deployment

| Feature | What was built | Where |
|---|---|---|
| **Name** | Everything renamed **HEALTH-01**: web, API, iOS, Android, docs | `web/src/config.ts`, `backend/app/core/config.py`, apps |
| **Landing page** | Public page from the team's sketch mockup: night-sky notebook, hand-drawn doodles, sleepy-moon sketch, Al Amerat mountains photo. Relevant facts only (how it works, what it tracks, AI with real numbers, NASA resources, apps, team); every button leads to the demo at `/app`. | `web/src/landing/` |
| **AI menu group** | Health Insights, Assistant, Models and Fine-tuning under one **AI** heading; sidebar grouped into Monitoring / AI / Data & connections / Tools | `web/src/components/Layout.tsx` |
| **Serious edition** | Private **separate deployment** (own ports 9080/9000, own database) behind a site password, same sketch UI with less text, tablet layout | `deploy/serious/`, `web/nginx.serious.conf`, `backend/app/site_gate.py` |
| **First-visit walkthrough** | 5-step sketch tour shown once per browser (cookie), not in the desktop app | `web/src/components/Onboarding.tsx` |
| **Device pairing** | Each phone has its own UUID shown in the app. It enrols as *pending*, an operator assigns it to a crew member on the **Devices** page, and uploads are credited to that person only (the phone cannot choose). Revoke and reset supported. Device secret stored hashed. | `backend/app/devices/`, `web/src/pages/Devices.tsx` |
| **Server connectors** (separate code base) | Adaptive "add a URL" connections. NOAA space weather (live Kp and ≥10 MeV protons mapped to the NOAA G/S storm scales, as context for the radiation hazard), another HEALTH-01 server, an Ollama/LLM server, or any JSON URL. New connectors drop into a folder. | `servers/`, `web/src/pages/Servers.tsx` |
| **Phone apps, simplified** | Three tabs: **Connect** (server URL + device ID + status), **Health** (Apple Health / Health Connect sync + fatigue check-in), **Exercise** (on-device rep counting: Apple Vision body pose on iPhone, ML Kit pose on Android; frames never leave the phone) | `ios/`, `android/` |
| **Desktop app** (Electron) | Shows the normal website from any server: saved servers, add a URL, start the local Docker stack, open in browser. Local AI model manager: list, download with progress, delete Ollama models. | `desktop/` |
| **LLM fine-tuning system** | Source inventory with licences, collectors with provenance, extractive instruction dataset, RAG search, QLoRA/LoRA training, evaluation harness, automatic run cards, version registry, deploy-to-Ollama, trainer service, Fine-tuning page with upload / train / monitor / evaluate / deploy / model management | `llm/`, `backend/app/llm_api/`, `web/src/pages/FineTuning.tsx`, `docs/llm/` |
| **Online deployment** | DigitalOcean: one setup script, GPU or CPU droplet, Ollama + trainer + Caddy HTTPS, firewall, random secrets | `deploy/digitalocean/`, `docs/DEPLOY_DIGITALOCEAN.md` |
| **Walkthrough** | Setup for every part, all stored locally | `docs/SETUP_WALKTHROUGH.md` |

### 1.5 Latest round

| Feature | What changed | Where |
|---|---|---|
| **Menu** | Groups: Monitoring · AI · Connect · Tools, with Settings pinned at the bottom | `web/src/components/Layout.tsx` |
| **Settings** | NASA hazards & risks, NASA research, and About (Team Amerat-01, made by Hajid Alkindi) moved here | `web/src/pages/Settings.tsx` |
| **Roles** | Mission control sees the crew overall but not single-astronaut dashboards | Layout, routes, overview |
| **Serious edition** | Simulated crew shown by full names (e.g. Lena Vasquez) with a "simulated" badge | `web/src/api.ts` |
| **Models** | All 8 models are on by default and preloaded at startup | `ai/models/*/manifest.json`, `backend/app/ai_engine/service.py` |
| **Simulator** | Renamed. Runs every model at the end of each simulated day and shows a live *Model responses* table. Tests check the direction of each response: illness-like and cardio scenarios raise the illness signal to caution, sleep disruption moves the sleep model, and every model runs. | `web/src/pages/Simulator.tsx`, `ai/tests/test_simulator_scenarios.py` |
| **Habitat sensors (MQTT)** | Mosquitto broker in the stack. Topics are discovered automatically and assigned to a metric with a JSON field, unit preset, data class and rate limit. Includes a demo publisher (simulated) and a guide. | `backend/app/mqtt/`, `web/src/pages/Habitat.tsx`, `docs/MQTT_HABITAT.md` |
| **Docs** | 5-minute deck, 30-second video, bullet points; screenshots of every screen | `docs/report/SHORT_FORMATS.md`, `docs/screenshots/` |

## 2. How each part uses the NASA challenge resources

| Challenge resource | Used for | Where in HEALTH-01 |
|---|---|---|
| HRP "Five hazards of human spaceflight" | Every alert and insight is tagged with its hazard (isolation, radiation, distance, gravity, hostile environment) | Hazards & Risks page, alert cards, assistant context |
| HRP risk pages (sleep, cardiovascular, bone, immune, SANS, behavioural, nutrition and more) | Metric-to-risk mapping; RAG passages; fine-tuning data (213 passages) | `data/challenge_snapshot/pages.json`, `llm/` corpus |
| HRP evidence reports and OCHMO briefs (Fracture, Cardiovascular, Degenerative, Nutrition, Bone Loss, Venous Thrombosis, Risk Approach Plans) | 14 checked numeric facts with page numbers; 1,484 passages for RAG and fine-tuning | Research page, `evidence.json`, `llm/` corpus |
| NASA OSDR (OSD-569, OSD-575, Inspiration4) | Real crew blood-panel data for context; reference ranges such as fasting glucose 65–99 mg/dL in the glucose model | NASA Research page, `glucose_metabolic` model |
| Standard Measures / Artemis II, CIPHER, sleep and immune studies (ongoing-research pages) | Chose which measurements HEALTH-01 collects: HR, HRV, BP, sleep, fatigue, glucose, body mass, exercise | Metric catalog, phone apps |
| Space radiation pages (NASA, CSA) | NOAA space-weather connector shows live storm scales as radiation-hazard context | Servers page |
| Exercise countermeasure pages | Exercise programs and guidance; bone-loss fact (1–1.5% per month) in the assistant and the model's training data | Exercise page, `pol-06`, evidence set |

Rule kept throughout: **NASA material is context and evidence, not training labels for astronaut predictions.** The challenge resources contain no wearable time series to train on, so the models are trained on Earth datasets and labelled as such.

## 3. Language model results
See [`docs/llm/RESULTS.md`](../llm/RESULTS.md) for the measured baseline of Qwen2.5 7B, the smoke-test fine-tuning run, and what is still to do on the GPU droplet.

## 4. Tests and checks run

| Check | Result |
|---|---|
| Backend tests | 65 passed (local run, includes device, server, LLM and site-gate tests) |
| AI-engine tests | 21 passed |
| New tests | Device enrolment / assignment / upload / revoke; server connections; LLM dataset is extractive and split by document; LLM API (upload validation, run registry, hyperparameter limits, trainer-missing handling) |
| Web type-check | `tsc -b` passes |
| Android | `gradlew assembleDebug` **builds** (`app-debug.apk`); not yet run on a phone |
| iOS | Written against iOS 17 APIs; **not compiled** (needs a Mac with Xcode) |
| Desktop | Electron launches; the connect page and the demo load (smoke mode) |
| Live checks | NOAA connector returned real Kp and proton flux; the Ollama connector listed the local models; landing page has no horizontal scroll at 375 px |

## 5. Limitations and honest notes

- **No astronaut data trained anything.** All models use Earth research data or simulation; the app says so next to each result.
- **iOS is uncompiled.** Android compiles but hasn't been tested on a device. Camera rep counting on phones is new and unvalidated.
- **The LLM is not fine-tuned at 7B yet.** A real QLoRA run on Qwen2.5 0.5B finished on the laptop GPU (validation loss 0.146, 54 min), proving the pipeline. The 7B run needs a 16–24 GB GPU (the DigitalOcean RTX 4000 Ada plan).
- **Baseline 7B failed 2 of 8 safety probes:** it gave a drug dose and invented a NASA report title.
- **The fine-tuned 0.5B matched sources much better** (F1 0.86 vs 0.39) **but failed 6 of 8 safety probes** and invented citation details. Not deployable.
- **The evaluation found a dataset flaw** (citation metadata missing from the context), fixed in `spacemed-v2`. The probes gate deployment for exactly this reason.
- **The LLM evaluation is small** (tens of items) and lexical (F1, ROUGE, number checks). It says nothing about clinical correctness.
- **Europe PMC abstracts are single studies**, many in animals, cells or ground analogs. The dataset adds a caveat to every one.
- **The serious edition is the same code** with a password gate and less text, deployed separately, so features stay in sync.
- **Device enrolment is open.** Phones can't upload until an operator assigns them, but a public server should still be watched for unknown pending devices.
