# Model card: Illness-related resting heart rate change

| | |
|---|---|
| ID / version | `illness_rhr` v1.0.0 |
| Category | illness |
| Status | ready |
| Enabled by default | True |
| Evidence level | Earth-based research data (not astronauts) |
| Validated on astronaut data | **no** |
| Execution | server, desktop, device; provider local; timeout 5.0 s |

**What it does.** Flags a resting heart rate well above the astronaut's own 28-day baseline, a change that often accompanies the onset of infections.

**Intended use.** Early, non-diagnostic prompt to re-check and report how the astronaut feels.

**Not intended for.** Diagnosing COVID-19 or any illness; clinical decisions.

## Dataset(s)
- **Stanford smartwatch COVID-19 wearables** - https://medrxiv.org/content/10.1101/2020.07.06.20147512v1  
  Licence: No explicit licence; public research release. Used for evaluation only, not redistributed.. Population: smartwatch users, USA. Citation: Mishra T. et al. Nat Biomed Eng 4, 1208-1220 (2020)

## Inputs
| Metric | Unit | Required | Min days | Max staleness (days) |
|---|---|---|---|---|
| resting_heart_rate | bpm | True | 15 | 2.0 |

## Outputs
- `z`: robust z-score of today's resting HR vs the previous 28 days
- `resting_hr`: bpm
- `baseline_rhr`: bpm
- `previous_day_z`: robust z or null

## Training / evaluation method and actual metrics
Data: 117 participants, 64 labelled illness events (COVID-19: 32, other illness: 32).
Protocol: participants randomly split 50/50 (seed 42); threshold chosen on the tuning half with a rule fixed in advance (max sensitivity with <= 1 false-alert episode / 30 healthy days). Event window [-7, 7] days around symptom onset; healthy days are >= 21 days from any reported illness.

| Detector | Threshold | Consecutive days | Events | Sensitivity | Day specificity | False-alert episodes / 30 healthy days | Median alert vs onset (days) | % detected before onset |
|---|---|---|---|---|---|---|---|---|
| rhr_z (selected on tuning half) | 3.0 | 1 | 19 | 0.474 | 0.954 | 0.852 | 1.0 | 33.3 |
| rhr_z (**held-out half (reported)**) | 3.0 | 1 | 24 | 0.792 | 0.9584 | 1.018 | -1.0 | 52.6 |
| rhr_z (all participants) | 2.0 | 1 | 43 | 0.814 | 0.9044 | 1.957 | -3.0 | 60.0 |
| rhr_z (all participants) | 2.0 | 2 | 43 | 0.465 | 0.9707 | 0.493 | -1.0 | 55.0 |
| rhr_z (all participants) | 2.5 | 1 | 43 | 0.767 | 0.9335 | 1.388 | -2.0 | 54.5 |
| rhr_z (all participants) | 2.5 | 2 | 43 | 0.326 | 0.9807 | 0.309 | 1.5 | 21.4 |
| rhr_z (all participants) | 3.0 | 1 | 43 | 0.651 | 0.9563 | 0.938 | 0.0 | 46.4 |
| rhr_z (all participants) | 3.0 | 2 | 43 | 0.209 | 0.9879 | 0.19 | 1.0 | 22.2 |
| rhr_z (all participants) | 3.5 | 1 | 43 | 0.488 | 0.9682 | 0.71 | 1.0 | 33.3 |
| rhr_z (all participants) | 3.5 | 2 | 43 | 0.093 | 0.9919 | 0.157 | 1.5 | 25.0 |
| rhr_z_actadj (all participants) | 2.0 | 1 | 43 | 0.791 | 0.926 | 1.718 | -2.0 | 55.9 |
| rhr_z_actadj (all participants) | 2.0 | 2 | 43 | 0.372 | 0.9835 | 0.38 | 1.0 | 43.8 |
| rhr_z_actadj (all participants) | 2.5 | 1 | 43 | 0.605 | 0.9556 | 1.101 | 0.0 | 38.5 |
| rhr_z_actadj (all participants) | 2.5 | 2 | 43 | 0.163 | 0.9923 | 0.176 | 1.0 | 28.6 |
| rhr_z_actadj (all participants) | 3.0 | 1 | 43 | 0.419 | 0.973 | 0.688 | 0.5 | 22.2 |
| rhr_z_actadj (all participants) | 3.0 | 2 | 43 | 0.093 | 0.996 | 0.094 | 1.5 | 0.0 |
| rhr_z_actadj (all participants) | 3.5 | 1 | 43 | 0.302 | 0.9835 | 0.441 | 1.0 | 15.4 |
| rhr_z_actadj (all participants) | 3.5 | 2 | 43 | 0.093 | 0.9982 | 0.05 | 1.5 | 0.0 |
| legacy_iforest (all participants) | 0.571 | 1 | 46 | 0.457 | 0.9818 | 0.441 | 0.0 | 47.6 |
| legacy_iforest (all participants) | 0.571 | 2 | 46 | 0.152 | 0.9968 | 0.065 | 1.0 | 42.9 |

## Alerting
Emits alerts: True; concern at severity >= caution; cooldown 24.0 h; thresholds {'caution_z': 3.0, 'info_z': 2.5}.

## Limitations
- Small number of illness events; wide uncertainty on sensitivity.
- Self-reported illness dates; other unreported illnesses may sit in 'healthy' days.
- Earth population, consumer smartwatches; not validated on astronauts.
- Detects physiological change consistent with illness; it does not diagnose illness.
