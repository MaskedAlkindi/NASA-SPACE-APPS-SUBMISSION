# Model card: Personal anomaly detection (original, simulation-trained)

| | |
|---|---|
| ID / version | `legacy_anomaly` v1.0.0 |
| Category | anomaly |
| Status | ready |
| Enabled by default | True |
| Evidence level | Simulated data only |
| Validated on astronaut data | **no** |
| Execution | server, desktop; provider local; timeout 10.0 s |

**What it does.** The original Isolation Forest on personal-baseline z-scores of resting HR, HRV, sleep and steps.

**Intended use.** Flag unusual combinations of daily measurements.

**Not intended for.** Clinical diagnosis or treatment decisions.

## Dataset(s)
- **Synthetic crew generator (ml/datasets/synthetic.py)** - this repository  
  Licence: project licence. Population: simulated. Citation: 

## Inputs
| Metric | Unit | Required | Min days | Max staleness (days) |
|---|---|---|---|---|
| resting_heart_rate | bpm | True | 7 | 2.0 |
| hrv_sdnn | ms | False | 1 | 2.0 |
| sleep_duration | h | False | 1 | 2.0 |
| steps | count | False | 1 | 2.0 |

## Outputs
- `percentile`: vs nominal simulated days
- `missing`: inputs missing

## Training / evaluation method and actual metrics
Simulated evaluation (see docs/AI_MODELS.md): {"roc_auc": 0.9937, "precision": 0.5833, "recall": 0.9333, "false_positive_rate": 0.0254, "n": 816, "n_positive": 30}
Real-data check for legacy_anomaly: see illness_rhr report rows `legacy_iforest`.

## Alerting
Emits alerts: False; concern at severity >= caution; cooldown 24.0 h; thresholds {}.

## Limitations
- See model code and report.
