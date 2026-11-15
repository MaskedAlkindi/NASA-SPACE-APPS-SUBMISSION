# Model card: Fatigue & stress from wearables (PMData)

| | |
|---|---|
| ID / version | `fatigue_pmdata` v1.0.0 |
| Category | fatigue |
| Status | ready |
| Enabled by default | True |
| Evidence level | Earth-based research data (not astronauts) |
| Validated on astronaut data | **no** |
| Execution | server, desktop; provider local; timeout 10.0 s |

**What it does.** Estimates the chance of a more-tired-than-usual (and more-stressed-than-usual) day from resting HR, sleep and activity relative to the person's own baseline. Trained on real self-reports.

**Intended use.** Weak hint and a prompt to complete a fatigue check-in; feeds conservative exercise guidance.

**Not intended for.** Measuring fatigue; fitness-for-duty decisions; diagnosis.

## Dataset(s)
- **PMData** - https://datasets.simula.no/pmdata  
  Licence: CC BY-NC 4.0 per OSF licence.txt (Simula page states CC BY 4.0; stricter terms applied). Population: 16 healthy adults, Norway. Citation: Thambawita V. et al. PMData: A Sports Logging Dataset. MMSys '20. doi:10.1145/3339825.3394926

## Inputs
| Metric | Unit | Required | Min days | Max staleness (days) |
|---|---|---|---|---|
| resting_heart_rate | bpm | True | 8 | 2.0 |
| sleep_duration | h | True | 8 | 2.0 |
| sleep_efficiency | % | False | 1 | 2.0 |
| sleep_midpoint | h | False | 1 | 2.0 |
| steps | count | False | 1 | 2.0 |
| exercise_minutes | min | False | 1 | 2.0 |

## Outputs
- `p_more_tired_than_usual`: probability 0-1
- `p_more_stressed_than_usual`: probability 0-1
- `features`: feature values used

## Training / evaluation method and actual metrics
Leave-one-subject-out over 16 participants. Label direction check (Spearman with readiness): {'fatigue': 0.399, 'stress': 0.099}.

| Target | Feature set / model | Days | Positives | AUC pooled | AUC within person (median) | Balanced acc. @0.5 | Brier |
|---|---|---|---|---|---|---|---|
| tired | wearable/logistic | 1659 | 544 | 0.505 | 0.559 | 0.5 | 0.2615 |
| tired | wearable/gbm | 1659 | 544 | 0.545 | 0.586 | 0.537 | 0.2552 |
| tired | wearable+yesterday_report/logistic | 1659 | 544 | 0.582 | 0.621 | 0.571 | 0.2489 |
| tired | wearable+yesterday_report/gbm | 1659 | 544 | 0.621 | 0.612 | 0.59 | 0.2368 |
| tired | baseline/yesterday_report | 1659 | 544 | 0.615 | 0.572 | 0.607 | 0.3175 |
| tired | baseline/constant |  |  | 0.5 |  |  |  |
| stressed | wearable/logistic | 1659 | 406 | 0.548 | 0.57 | 0.549 | 0.261 |
| stressed | wearable/gbm | 1659 | 406 | 0.535 | 0.552 | 0.526 | 0.2533 |
| stressed | wearable+yesterday_report/logistic | 1659 | 406 | 0.649 | 0.61 | 0.619 | 0.2342 |
| stressed | wearable+yesterday_report/gbm | 1659 | 406 | 0.64 | 0.643 | 0.619 | 0.2158 |
| stressed | baseline/yesterday_report | 1659 | 406 | 0.682 | 0.626 | 0.671 | 0.2207 |
| stressed | baseline/constant |  |  | 0.5 |  |  |  |

Deployed (wearable-only): tired: gbm, AUC 0.545; stressed: logistic, AUC 0.548

## Alerting
Emits alerts: True; concern at severity >= caution; cooldown 24.0 h; thresholds {'info_probability': 0.6}.

## Limitations
- 16 healthy adults (Norway), Fitbit Versa 2: small, Earth-based, not astronauts.
- Self-reported labels; 'tired' means more tired than that person's normal.
- Fitbit active minutes stand in for 'exercise minutes'; device differences are not modelled.
