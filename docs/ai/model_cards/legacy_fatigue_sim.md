# Model card: Fatigue estimate (original, simulation model)

| | |
|---|---|
| ID / version | `legacy_fatigue_sim` v1.0.0 |
| Category | fatigue_simulated |
| Status | ready |
| Enabled by default | True |
| Evidence level | Simulated data only |
| Validated on astronaut data | **no** |
| Execution | server, desktop; provider local; timeout 10.0 s |

**What it does.** Samn-Perelli 1-7 fatigue estimate trained on synthetic labels.

**Intended use.** Demonstration only.

**Not intended for.** Clinical diagnosis or treatment decisions.

## Dataset(s)
- **Synthetic crew generator (ml/datasets/synthetic.py)** - this repository  
  Licence: project licence. Population: simulated. Citation: 

## Inputs
| Metric | Unit | Required | Min days | Max staleness (days) |
|---|---|---|---|---|
| sleep_duration | h | True | 3 | 2.0 |
| workload_tlx | score 0-100 | False | 1 | 2.0 |
| fatigue_score | score 1-7 | False | 1 | 3.0 |

## Outputs
- `inputs`: feature values
- `missing`: missing inputs

## Training / evaluation method and actual metrics
Simulated evaluation (see docs/AI_MODELS.md): {"mae": 0.5209, "rmse": 0.6694, "r2": 0.6078, "n": 960}
Real-data check for legacy_anomaly: see illness_rhr report rows `legacy_iforest`.

## Alerting
Emits alerts: False; concern at severity >= caution; cooldown 24.0 h; thresholds {}.

## Limitations
- See model code and report.
