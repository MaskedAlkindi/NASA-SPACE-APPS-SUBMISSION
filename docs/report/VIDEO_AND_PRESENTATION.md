# HEALTH-01: 30-minute video and presentation notes

Tone: curious, honest, a bit funny. The running joke is *the space donkey*, from Hajid's drawing: he is the user who asks the "simple" questions.
Rule for every claim on screen: **say where the number came from.**

The 30-second video script, as spoken bullets, is in [SHORT_FORMATS.md](SHORT_FORMATS.md), section B. The 5-minute slides are `HEALTH-01_5_minutes.pptx`: the points are the bullets, and each speaker note defines the terms. This file is the longer talk.

---

## Run of show (30 min)

| Time | Segment | On screen |
|---|---|---|
| 0:00–2:00 | Cold open | Space-donkey drawing + sleepy moon |
| 2:00–5:00 | The problem, using NASA's own words | HRP five hazards page |
| 5:00–8:00 | What HEALTH-01 is | Landing page, scroll |
| 8:00–13:00 | Live demo 1: a crew member's day | Phone → dashboard → exercise → nutrition |
| 13:00–18:00 | Live demo 2: mission control | Alerts, devices, servers, NOAA |
| 18:00–23:00 | The AI that shows its work | Models page, model cards, fine-tuning |
| 23:00–26:00 | How we used the NASA resources | Resource map figure |
| 26:00–28:30 | What broke and what we learned | Bug wall |
| 28:30–30:00 | What's next + thanks | Team, roadmap |

## Segment bullets

### 0:00 Cold open
- "Your watch knows your heart rate. Up there, nobody knows what *normal* is any more, including your heart."
- "Meet the space donkey. He's our test user. He doesn't read papers. He asks: *am I OK?*"
- Title card: **HEALTH-01: health tracking for the people on board.**

### 2:00 The problem
- Read the five hazards straight off NASA's HRP page: isolation, radiation, distance from Earth, altered gravity, hostile closed environment.
- One hard number on screen: weight-bearing bones lose **about 1–1.5% of mineral density per month** in spaceflight (NASA evidence report on fracture risk, page 4).
- "Same body, new physics. So we compare each astronaut to **their own** baseline, not to an Earth average."

### 5:00 What it is
- Four doors in: website, desktop app, iPhone, Android. One server.
- "The phones do two jobs only: collect wearable data, count reps. Everything clever happens on the server."
- Scroll the landing page: every number has a dataset name under it. "No mystery percentages."
- What you will pass: the film, how it works, the puzzle, exercise, the food log, the model cards, the NASA feature cards, the demo crew. References is a separate page from the menu. Skip "About Amerat" and the empty gallery. Both are still blank.

### 8:00 Live demo 1: a crew member's day
- Phone shows its device ID, the operator assigns it, the phone says "Connected as VEGA". **(Funny beat: "pairing a phone, now with less Bluetooth suffering.")**
- Health sync, then the dashboard: resting HR, HRV, sleep, glucose, each with a baseline band.
- Fatigue check-in (Samn-Perelli 1–7). "The phone asks how you feel, because our wearable-only fatigue model is honestly weak (AUC 0.55) and *we say that on screen*."
- Exercise **Today**: the readiness card says "Go for training" or "Train lighter today", with reasons. Do 5 squats on camera; the counter goes up; save. **(Donkey joke: four legs, double the squats.)**
- Nutrition: open the food log. The rings are example marks, not a menu. Point at fluid and body mass, and at the nutrition-report lines under the chart (2.4% body mass per 100 days, urine volume about 17% lower).

### 13:00 Live demo 2: mission control
- Alert with evidence: value, baseline, z-score, related NASA risk, recommended follow-up, and "not a diagnosis".
- Devices page: pending phones, assign, revoke.
- Servers page: live **NOAA space weather**, today's Kp index and proton flux on the NOAA storm scales. "The radiation hazard, live, from a real government feed."
- Serious edition: same sketch, less text, behind the site password, on its own ports. "Same brain, quieter room." Do not call it a different design.

### 18:00 The AI that shows its work
- Models page: each model card says the data, the population, the licence and whether it's validated on astronauts. For all of them the answer is **no**, and we say so.
- Real numbers: illness signal caught **79% of 24 held-out illness episodes**, about 1 false alarm a month; glucose insulin-resistance flag AUC **0.83**; HR from beats within **1.1 bpm** of the device.
- "We also turned one model *off*, because it wasn't good enough (orthostatic, r ≈ 0.5). Knowing when not to ship is a feature."
- Fine-tuning is two attempts. Keep a run only at 6/8 probes or better and unsupported numbers at or under 2%.
- Attempt 1, the laptop (RTX 2060, 6 GB): the 7B does not fit, so it stays untuned (F1 0.39, unsupported numbers 2%, probes 6/8). A 0.5B smoke test scored F1 0.86 and passed 2/8. That is where the bar came from.
- Attempt 2, after the hardware switch (RTX 6000 Ada, 48 GB, spacemed-v2). The 7B was not trained again. Untuned 7B / 14B / 32B: F1 about 0.40, probes 6/8, unsupported numbers 7.3%, 7.3%, and 2.4%.
- **Keep the 14B QLoRA:** F1 0.92, ROUGE-L 0.92, unsupported numbers 0%, probes 6/8. **Discard the 32B QLoRA:** F1 0.93, probes 4/8. It invented an ibuprofen dose and "about 9% of long-duration crew develop kidney stones," both as NASA quotes.
- The 14B still fails two probes. Asked about a fake "9 hours of sleep" study, it cites "NASA, 2024". It is not the live assistant yet.
- One-liner: "The bigger model scored higher, and we threw it out."

### 23:00 NASA resources → features
Walk the resource-map figure (Figure 5 in DRAWIO_FIGURES.md):

| NASA resource | Becomes |
|---|---|
| Hazards | Alert tags |
| Risk pages | RAG and fine-tuning passages |
| Evidence reports | 14 checked facts with page numbers |
| OSDR Inspiration4 | Real crew lab context |
| Standard Measures | What we measure |
| Nutrition evidence report | Food log: body mass and fluid |

### 26:00 What broke (makes it human)
- The CVES dataset publishes blood-pressure change as *sit minus stand*. Our first plot said everyone's BP went *up* when standing. **(Donkey: "so standing is relaxing?")** We found the sign, checked it at r = 0.993, fixed it, and still turned the model off.
- MMASH sleep times had no seconds; our parser cried.
- The Stanford illness labels weren't in the data zip; they were hiding in the paper's supplementary spreadsheet.
- A background AI job slowed the simulator until a test caught it. Now it waits for data to go quiet.
- Windows line endings vs. our scripts: a classic.

### 28:30 Next
- Real analog or astronaut data through a NASA data request: the one thing that turns "Earth-validated" into "crew-validated".
- Finish deploying the 14B fine-tune when the demo is quiet, then check that deployed copy before it becomes the assistant. The next dataset needs many more examples with no source passage, so the model stops inventing one.
- Field-test the phone rep counter.
- Thank-yous; NASA Space Apps; Al Amerat.

---

## Slide deck outline (10–12 slides)

1. **Title:** HEALTH-01, Team Amerat 01, the space donkey.
2. **Problem:** five hazards (NASA quote) and the bone-loss number with its page.
3. **Idea:** personal baselines, explained evidence, humans in the loop.
4. **System diagram** (Figure 1).
5. **Phones and pairing** (Figure 3).
6. **AI engine and real results table** (Figure 4 plus numbers).
7. **The LLM pipeline** (Figure 6). On the slide: the five-model table, and the line "Kept the 14B. The 32B scored higher and failed the probes."
8. **NASA resources → features** (Figure 5).
9. **Safety and honesty:** not a diagnosis, evidence levels, the model we turned off.
10. **Deployment:** local, serious edition, desktop, online demo on a GPU droplet (Figure 7).
11. **What broke / what we learned.**
12. **Next steps + team.**

## Catchy lines (pick a few)
- "Normal is a moving target at 400 km."
- "Every number has a home address."
- "Not a doctor. A very organised notebook."
- "We measured our own models, and benched one."
- "Your data, your baseline, your flight surgeon."
- "The phone counts squats; the server counts on evidence."
