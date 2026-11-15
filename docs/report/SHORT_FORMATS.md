# Short formats

## A. 5-minute presentation

The slides are `HEALTH-01_5_minutes.pptx`. Eight slides. The bullets on the slide are the points. In PowerPoint, View → Notes. Each note has the lines to say, then a **Terms** block that defines every piece of jargon on that slide in plain language.

| Time | Slide | Bullets on the slide |
|---|---|---|
| 0:00 | HEALTH-01 | health tracking for the people on board. own days, not Earth. Team Amerat 01. |
| 0:20 | up there, normal moves. | five hazards. bone about 1–1.5% a month. Earth cutoff is the wrong comparison. |
| 1:00 | gather. compare. explain. | phone and watch send the day. server uses this person's earlier days. an alert names the evidence. a person decides. |
| 1:45 | earth research. not astronauts yet. | Stanford 79% and about 1 false alert in 30 healthy days. glucose AUC 0.83. heart rate within 1.1 bpm. fatigue AUC 0.55, so we ask. |
| 2:35 | one can alert. one is off. | illness may alert. glucose and fatigue stay informational. orthostatic measured, then switched off. |
| 3:15 | the phone counts. the food log too. | nine movements. the video stays on the phone. meals, fluid and body mass. example marks, not a menu. |
| 4:00 | two attempts. we kept the 14B. | 6 of 8 probes, invented numbers at or under 2%. laptop 7B was the bar. 14B kept. 32B set aside. not the live voice yet. |
| 4:45 | every number has a home address. | not a medical device. not validated on astronauts. the 14B is not live yet. |

The clock in the corner of each slide is the target, not something to read aloud. Definitions of baseline, AUC, QLoRA, F1, probe, MediaPipe, HealthKit, and Health Connect are in the notes, not on the slide.

## B. 30-second video

The slides are `HEALTH-01_30_seconds.pptx`. Read the bullets in order. About 65 words, which is the 30 seconds if you keep a clear pace. Do not add the glucose number, the fatigue number, or the model names. Those belong in the 5-minute talk.

| Time | Say these bullets |
|---|---|
| 0–8 s | Astronauts get sick a long way from a hospital. We compare each person to their own baseline, not to people on Earth. |
| 8–20 s | Stanford wearables: 79 percent of illness episodes, caught early. About one false alert in thirty healthy days. Earth research. Not astronauts yet. |
| 20–27 s | Exercise on the phone: the camera counts the reps, the video stays on the phone. The food log tracks meals, fluid and body mass. Example marks, not a menu. |
| 27–30 s | A person still decides. Not a medical device. Health tracking for the people on board. |

Drop the screen recording on slide 3 before you record. Do not count squats live in this cut. Do not explain baseline, Stanford, or MediaPipe here. If the recording ends early, one spare line is enough: the website uses MediaPipe in the browser, the iPhone only reads HealthKit, Android only reads Health Connect.

**Before you hit record**

1. Demo crew only. Do not show a personal watch.
2. Exercise is the screen recording. Put it on slide 3 before you present. Do not record the camera live in this 30 seconds.
3. Record at 60 fps. Read the bullets on each slide and nothing else. The recording plays on slide 3.
4. End on "a person still decides." Do not open a fifth topic.

**If a judge asks about the 7B, 14B, or 32B**

Two attempts. A run is kept only at 6 of 8 probes or better, and unsupported numbers at or under 2%.

Attempt 1, the laptop (RTX 2060, 6 GB, dataset spacemed-v1). A 7B fine-tune does not fit, so the 7B was scored untuned and a 0.5B was trained to prove the pipeline. Untuned 7B: F1 0.39, unsupported numbers 2%, probes 6 / 8. That is the bar. The 0.5B: F1 0.86, unsupported numbers 17%, probes 2 / 8. Discarded. It invented citations.

Attempt 2, after the hardware switch (one RTX 6000 Ada, 48 GB, dataset spacemed-v2). The 7B was not trained again. The 32B was trained first, then the 14B.

| | F1 | Unsupported numbers | Probes | Keep? |
|---|---|---|---|---|
| 7B, no fine-tune | 0.41 | 7.3% | 6 / 8 | no |
| 14B, no fine-tune | 0.40 | 7.3% | 6 / 8 | no |
| 32B, no fine-tune | 0.40 | 2.4% | 6 / 8 | no |
| **14B + QLoRA** | **0.92** | **0%** | **6 / 8** | **yes** |
| 32B + QLoRA | 0.93 | 0% | 4 / 8 | no |

The 7B was not fine-tuned. The 32B invented an ibuprofen dose and a kidney-stone percentage and presented both as NASA quotes. The 14B is the keeper, and it still writes a fake 2024 sleep study when a question has no source. It is not the voice in the live demo yet. Say the numbers above and do not add any others.

## C. Bullet points (for posts, the submission form, judges)

- **What:** astronaut health tracking that compares each person with their own baseline, including exercise and a food log.
- **How:** phones and watches feed a server; models explain changes with evidence.
- **Built on NASA:** the 5 hazards, HRP risk pages and evidence reports (with page numbers), OSDR crew data.
- **AI that shows its work:** models trained on real research data; one we switched off because it wasn't good enough.
- **Real numbers:** 79% of illness episodes flagged early; metabolic pattern AUC 0.83; heart rate within 1.1 bpm.
- **Runs anywhere:** web, iPad, iPhone, Android, desktop, a private GPU server.
- **Honest:** research prototype, not a medical device, not yet validated on astronauts.
