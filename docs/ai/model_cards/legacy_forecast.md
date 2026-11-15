# Model card: 7-day trend forecast (original)

| | |
|---|---|
| ID / version | `legacy_forecast` v1.0.0 |
| Category | forecast |
| Status | ready |
| Enabled by default | True |
| Evidence level | Simulated data only |
| Validated on astronaut data | **no** |
| Execution | server, desktop; provider local; timeout 10.0 s |

**What it does.** Damped Holt forecasts of resting HR, sleep and HRV with 80% intervals.

**Intended use.** Trend context.

**Not intended for.** Clinical diagnosis or treatment decisions.

## Dataset(s)
- **Synthetic crew generator (ml/datasets/synthetic.py)** - this repository  
  Licence: project licence. Population: simulated. Citation: 

## Inputs
| Metric | Unit | Required | Min days | Max staleness (days) |
|---|---|---|---|---|
| resting_heart_rate | bpm | True | 10 | 3.0 |

## Outputs
- `series`: forecast points per metric

## Training / evaluation method and actual metrics
Simulated evaluation (see docs/AI_MODELS.md): {"resting_heart_rate": {"params": {"alpha": 0.05, "beta": 0.01, "phi": 0.7}, "residual_sd_h1": 2.654, "backtest": {"mae_model": 1.86, "mae_naive_last_value": 2.4962, "mae_mean_last_7d": 2.1763, "horizon_days": 7}}, "sleep_duration": {"params": {"alpha": 0.05, "beta": 0.01, "phi": 0.5}, "residual_sd_h1": 0.5808, "backtest": {"mae_model": 0.4397, "mae_naive_last_value": 0.6028, "mae_mean_last_7d": 0.4765, "horizon_days": 7}}, "hrv_sdnn": {"params": {"alpha": 0.05, "beta": 0.05, "phi": 0.5}, "residual_sd_h1": 5.2613, "backtest": {"mae_model": 4.0569, "mae_naive_last_value": 5.4885, "mae_mean_last
Real-data check for legacy_anomaly: see illness_rhr report rows `legacy_iforest`.

## Alerting
Emits alerts: False; concern at severity >= caution; cooldown 24.0 h; thresholds {}.

## Limitations
- See model code and report.
