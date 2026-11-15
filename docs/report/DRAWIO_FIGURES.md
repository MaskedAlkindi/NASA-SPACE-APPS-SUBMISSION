# Figures to draw in draw.io

**Make them look like ours, not generated:**

- **Style:** use draw.io's *Sketch* style (Format › Style › Sketch, "rough" lines) with the team colours: steel blue `#005c96`, constellation blue `#1d2bdb`, red `#d81b1b` for "01" and warnings, and ink `#17191f`.
- **Hand touches:** add the logo and one or two of the doodles (rocket, satellite, moon) in a corner. Write a few labels in a hand font (Kalam or Patrick Hand).
- **Real names:** every box carries a real folder or endpoint name from the repository, such as `backend/app/devices/` or `/api/v1/ai`. That is the strongest sign of real work.
- **Real history:** put dates and versions where they're true, for example "spacemed-v1 · 2026-11-14", "illness_rhr v1.0.0".
- **Mistakes on the diagram:** keep one "we tried this, it failed" note per figure where it applies.

---

### Figure 1: System overview (the one-slide picture)

| Layer | Boxes |
|---|---|
| **Left: collect** | iPhone (Apple Health + Vision rep counter) · Android (Health Connect + ML Kit) · Website camera · Cabin sensors / simulator |
| **Centre: server** | `FastAPI /api/v1` → Measurement store (PostgreSQL) → Personal baselines → Alerts · AI engine (`ai/`) · Assistant (OpenAI / Ollama / offline) · Exercise module |
| **Right: people** | Astronaut (own data) · Flight surgeon · Mission control |
| **Top: outside world** | NASA challenge resources · NASA OSDR · NOAA space weather (via `servers/`) · Ollama |
| **Bottom: clients** | Website (notebook + serious) · Desktop (Electron) |

Arrows carry their contract names: `devices/upload`, `exercise_guidance.v1`, `ai_assessment.v1`.

### Figure 2: Data journey of one heartbeat
Watch → HealthKit → phone app → `POST /devices/upload` (device UUID + token) → normalised measurement (unit, quality, data class) → daily summary → personal baseline (median / MAD, earlier days only) → AI models (after a 30 s quiet period) → assessment → concern? → alert with evidence → dashboard and assistant.

Margin note: "the phone never chooses whose data it is".

### Figure 3: Phone pairing (sequence diagram)
Lanes: Phone · Server · Operator.

1. Phone generates a UUID.
2. `register` → *pending*, plus a secret.
3. Operator opens Devices and assigns VEGA.
4. The phone's status poll says *assigned*.
5. Uploads are credited to VEGA.
6. Revoke → 403.

### Figure 4: AI engine plug-in architecture
`manifest.json` + `model.py` per folder → `ModelRegistry` (discover, enable/disable, lazy load, timeout) → `HealthDataView` (input checks) → `Assessment` → alerts adapter (concern / insight) and exercise adapter.

Side table: the 5 real-data models with dataset, people and key metric. Draw the orthostatic box greyed out with a "switched off: r ≈ 0.5" sticky note.

### Figure 5: NASA resources → HEALTH-01 features (mapping)
Two columns joined by lines:

| Left: NASA resources | Right: features |
|---|---|
| Five hazards | Alert tags |
| Risk pages | RAG and LLM training passages |
| Evidence reports | Checked facts with page numbers |
| OSDR OSD-569/575 | Crew lab context and glucose reference range |
| Standard Measures / CIPHER | What the phones collect |
| Radiation pages | NOAA space-weather connector |
| Exercise countermeasures | Exercise readiness and programs |

### Figure 6: LLM pipeline
`sources.json` (licences) → `collect.py` (2,170 passages + SHA-256) → `build_sft.py` (extractive, split by document → train 1,167 / val 81 / test 138) → QLoRA on Qwen2.5 → `RUN_CARD.md` → evaluation (F1, ROUGE-L, unsupported numbers, abstention, safety probes) → Ollama.

RAG branch from the corpus to the assistant. Label: "no model-written training text".

### Figure 7: Deployment options
Four boxes:

| Deployment | Contents |
|---|---|
| Laptop (Docker) | notebook :8080, API :8000 |
| Serious edition | :9080 / :9000, own database |
| Desktop app | points at any server; manages Ollama models |
| DigitalOcean GPU droplet | Caddy HTTPS → web → API → PostgreSQL; Ollama on the GPU; trainer on the GPU |

Price sticker: "RTX 4000 Ada, 20 GB: $0.76/h; switch on for demo day, destroy after".

### Figure 8: Exercise readiness decision
Decision tree from `ai/adapters/exercise.recommend`:

- Any warning → **Rest and re-check**
- Caution anomaly or alert → **Train lighter**
- Fatigue estimate → **Go / Lighter**
- No data → **Not enough data (check in)**

### Figure 9: Evidence levels (legend used everywhere)
Spaceflight · Earth research · Simulation · Rule-based, each with its badge colour. One example per level from the app.

### Figure 10: "What broke" timeline (for the video)
Dated bugs:

- CVES sign flip
- MMASH time format
- Stanford labels in the supplementary spreadsheet
- AI job slowing the simulator
- CRLF line endings

Draw each as a little crack in a hand-drawn timeline, with the fix underneath.

---

**Extra authenticity material to capture while recording:**

- the git log (`git log --oneline`)
- the model cards' dates
- a run card from the fine-tuning run
- the NOAA connector showing *today's* Kp
- a phone with its real device ID
- the Devices page assigning it
