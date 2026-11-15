# Limitations and future research

## What the evidence does and does not show

| | Earth research data | Simulated data | Spaceflight data |
|---|---|---|---|
| Used for | Training/evaluation of fatigue, glucose, illness, HRV/sleep and orthostatic work | Original demo models and the demo crew | Context only (NASA HRP risks and reports) |
| Validated on astronauts? | No | No | - |

- **Fatigue from wearables is weak.** PMData leave-one-subject-out AUC is about 0.55, so wearables alone barely predict self-reported fatigue. The model is informational only and pushes for a check-in.
- **Illness detection numbers are uncertain.** There are only 19–24 evaluable illness events per half, and sensitivity was 47% on the tuning half vs 79% on the held-out half. Self-reported dates and unreported illnesses add noise. A raised resting HR also follows poor sleep, stress, dehydration and exercise.
- **Glucose:** the CGM insulin-resistance flag has AUC 0.83 on 45 people, with a wide confidence interval. Astronauts in the app have daily fasting glucose, not CGM or meal logs, so those parts usually don't run. HOMA-IR needs a measured insulin value.
- **Orthostatic:** our blood-pressure changes agree only moderately with the published values (r ≈ 0.5). The prototype is disabled. Sit-to-stand in older adults on Earth says nothing about landing tolerance.
- **Domain shift:** NASA reports in-flight heart rate and blood pressure fall below pre-flight levels, and core temperature rises about 1 °C. Personal in-flight baselines help, but Earth-trained models have not been tested against these shifts.
- **Small samples everywhere:** 16, 45, 22 and 71 people, and 117 for the illness data.

## Next steps

1. Request NASA Spaceflight Standard Measures / HERA data through NASA's Life Sciences Data Archive and re-evaluate on astronaut or analog data.
2. Add CGM support to the mobile apps (HealthKit / Health Connect blood-glucose series) so the glucose model's CGM path can run.
3. Calibrate `fatigue_pmdata` per astronaut from their own Samn-Perelli check-ins (personalised fine-tuning), since the check-in is the stronger signal.
4. Collect a stand-test protocol (beat-to-beat BP) to make the orthostatic prototype usable, and validate it on a younger population.
5. A dedicated exercise AI model behind the `exercise_guidance.v1` contract.
