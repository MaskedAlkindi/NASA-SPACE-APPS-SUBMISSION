# Model card: Orthostatic response features (research prototype)

| | |
|---|---|
| ID / version | `orthostatic` v0.1.0 |
| Category | orthostatic |
| Status | research_prototype |
| Enabled by default | False |
| Evidence level | Earth-based research data (not astronauts) |
| Validated on astronaut data | **no** |
| Execution | server, desktop; provider local; timeout 10.0 s |

**What it does.** Computes blood-pressure and heart-rate responses to standing from a beat-to-beat stand test and checks the consensus orthostatic-hypotension and HR-rise criteria.

**Intended use.** Research exploration of NASA's primary return-to-gravity cardiovascular risk (orthostatic intolerance).

**Not intended for.** Predicting astronaut tolerance of re-entry or landing; diagnosis.

## Dataset(s)
- **CVES v1.0.0 sit-to-stand subset** - https://physionet.org/content/cves/1.0.0/  
  Licence: ODC-By v1.0. Population: older adults with/without stroke. Citation: Novak V. et al. Cerebral Vasoregulation in Elderly with Stroke (PhysioNet)

## Inputs
| Metric | Unit | Required | Min days | Max staleness (days) |
|---|---|---|---|---|
| stand_test | record | True | 1 | 30.0 |

## Outputs
- `delta_sbp`: mmHg
- `delta_dbp`: mmHg
- `delta_hr`: bpm
- `hr_peak_rise`: bpm
- `oh_criterion`: bool
- `hr_rise_criterion`: bool

## Training / evaluation method and actual metrics
signal-processing verification + descriptive statistics (research prototype). 71/71 recordings processed.
Agreement with the study's published sit-to-stand change (sign-aligned): {'seg_delta_sbp': {'n': 57, 'pearson_r': 0.529, 'mean_abs_diff_mmHg': 11.9, 'window': "whole 5-min segments (study's windows)"}, 'seg_delta_dbp': {'n': 57, 'pearson_r': 0.423, 'mean_abs_diff_mmHg': 6.5, 'window': "whole 5-min segments (study's windows)"}, 'delta_sbp': {'n': 57, 'pearson_r': 0.523, 'mean_abs_diff_mmHg': 11.3, 'window': 'first 3 min after standing (consensus OH window)'}, 'delta_dbp': {'n': 57, 'pearson_r': 0.473, 'mean_abs_diff_mmHg': 6.4, 'window': 'first 3 min after standing (consensus OH window)'}}
Consensus criteria met: {'oh_pct': 4.2, 'hr_rise_ge30_pct': 2.8}. Median changes: {'delta_sbp': 4.1, 'delta_dbp': 4.4, 'delta_hr': 7.9, 'hr_peak_rise': 12.4}.
Association with self-reported orthostatic symptoms (exploratory): {'n': 71, 'with_symptoms': 36, 'auc_sbp_drop': 0.571, 'auc_hr_rise': 0.433}

## Alerting
Emits alerts: False; concern at severity >= warning; cooldown 24.0 h; thresholds {}.

## Limitations
- Older adults with/without stroke, hypertension or diabetes - very different from astronauts.
- Sit-to-stand is a milder challenge than tilt or landing; symptoms are self-reported history, not during the test.
- Earth-based; does not establish astronaut return-to-gravity prediction accuracy.
