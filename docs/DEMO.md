# Five-minute demo script

**Before you present:** run `docker compose up -d --build`, open http://localhost:8080, and sign in as `mission-control` (`hmt-demo`). For a clean start, click Simulator → **Reset demo data** about 1 minute before.

## 0:00–0:40 · The problem and the idea (Mission Overview)

- "On a Mars mission, the nearest doctor is 20 light-minutes away. Astronauts need to understand their own health data, and the system must work offline."
- Point to the **mission day**, crew cards, active alerts and habitat environment.
- Point to the purple **SIMULATED** banner: "Every value is labelled real, NASA research, or simulated. We never blur that line."

## 0:40–1:40 · Personal baselines (Astronaut Dashboard → ATLAS)

- Resting HR is 76 bpm and flagged **above usual**. The shaded band is ATLAS's *own* 10–90% range, not a population norm.
- HRV dropped, while sleep and activity look normal. Scroll to the **baseline comparison** table.
- Switch to **VEGA**: sleep chart, sleep-timing variability (circadian-disruption indicator), fatigue climbing over the last week.

## 1:40–2:40 · AI intelligence (AI Intelligence → ATLAS)

- **Anomaly model:** the last three days are yellow, above the threshold. The contributor table shows exactly *why*: resting HR +7 z, HRV −4 z.
- **Fatigue model**, with its 80% interval and the "SIMULATION MODEL" label.
- **7-day forecasts** with uncertainty bands.
- Scroll to the **model cards**: metrics, the honest note that evaluation used simulated data, and the limitations.

## 2:40–3:30 · Live simulator (Simulator)

- Scenario `cardio_anomaly`, target **ORION** (currently healthy), 4 days, 0.3 s per simulated hour, then **Start replay**.
- Watch the live heart-rate stream. Day 1 is baseline. When the 07:00 readings arrive on day 2, alerts appear on the right: **"Unusual combination of measurements"** and **"Resting heart rate above your baseline"**, each with its evidence.
- Optional: run `co2_scrubber_fault` to show the CO₂ line crossing the caution and warning thresholds.
- Optional live pipeline: `.\scripts\mqtt_sim.ps1`, then Habitat sensors. Readings move every few seconds and stay labelled simulated. That is publisher → Mosquitto → the same ingest path as every other module.

## 3:30–4:20 · Assistant and NASA research

- **AI Assistant → VEGA:** click "Has my sleep been getting worse?" The answer separates what was measured from what the models estimate, cites NASA research as [R1]…, and includes escalation guidance.
- Show the badge: *offline explainer* (no internet needed) or the OpenAI model if a key is configured.
- **NASA Research:** the Inspiration4 lab explorer (real OSDR data: pick **WHITE BLOOD CELL COUNT** and show the 4 crew from pre-flight to R+1), the computed findings with their n=4 caveat, dataset provenance with DOI, and the HRP risk context.

## 4:20–5:00 · Modularity and mobile

- **Modules page:** six independent integrations with live status, all sharing one measurement schema. "Adding a new sensor is one file."
- Mobile: the iPhone app bridges HealthKit and the Android app bridges Health Connect. Each health permission is requested individually, and uploads land in the same pipeline (`pilot` account).
- Close: "Runs with one `docker compose up`, works offline, honest about uncertainty, and never pretends to be a doctor."

## Backup questions to try in the assistant

- "Why is my heart rate unusual?" (ATLAS)
- "What should I check next?"
- "I have chest pain, how am I doing?" (shows the forced escalation)
- "What does NASA research say about this risk?"
