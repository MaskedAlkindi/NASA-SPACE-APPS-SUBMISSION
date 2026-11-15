# Model card: Sleep & HRV recovery indicators

| | |
|---|---|
| ID / version | `sleep_hrv` v1.0.0 |
| Category | sleep_hrv |
| Status | ready |
| Enabled by default | True |
| Evidence level | Transparent rules on published reference values |
| Validated on astronaut data | **no** |
| Execution | server, desktop, device; provider local; timeout 5.0 s |

**What it does.** Sleep debt against the astronaut's own usual sleep, sleep-timing regularity, and HRV against a personal baseline, combined into a simple recovery indicator.

**Intended use.** Recovery context for the dashboard, assistant and exercise guidance.

**Not intended for.** Diagnosing sleep disorders.

## Dataset(s)
- **MMASH v1.0.0 (verification only)** - https://physionet.org/content/mmash/1.0.0/  
  Licence: ODbL v1.0. Population: 22 healthy young men. Citation: Rossi A. et al. MMASH, PhysioNet 2020, doi:10.13026/cerq-fc86

## Inputs
| Metric | Unit | Required | Min days | Max staleness (days) |
|---|---|---|---|---|
| sleep_duration | h | True | 7 | 2.0 |
| sleep_midpoint | h | False | 1 | 2.0 |
| hrv_sdnn | ms | False | 1 | 3.0 |
| hrv_rmssd | ms | False | 1 | 3.0 |

## Outputs
- `sleep_debt_7d_h_vs_own_median`: h
- `sleep_timing_sd_7d_h`: h
- `hrv_z`: robust z
- `hrv_metric`: hrv_sdnn or hrv_rmssd
- `recovery_indicator`: normal | watch | reduced

## Training / evaluation method and actual metrics
signal-processing verification (no model training).
HR from our RR processing vs ActiGraph HR: 22 people, 29993 minutes, median MAE 1.08 bpm, bias -0.19 bpm, r 0.988.
Sleep efficiency recomputed as TST / time in bed: max difference 0.0 percentage points (21 people).
Night RMSSD median 52.6 ms (IQR [41.2, 59.3]); artefact filter kept 78.8% of beats.
Exploratory correlations (uncorrected): {'night_rmssd_vs_Daily_stress': {'n': 19, 'spearman_rho': -0.27, 'p_value': 0.264}, 'night_rmssd_vs_STAI2': {'n': 19, 'spearman_rho': 0.244, 'p_value': 0.313}}

## Alerting
Emits alerts: True; concern at severity >= caution; cooldown 24.0 h; thresholds {'sleep_debt_h': 5.0, 'timing_sd_h': 1.0, 'hrv_low_z': -2.0}.

## Limitations
- 22 healthy young men, one day each: verification only, no generalisable model.
- Correlations are exploratory, uncorrected for multiple comparisons.
- Earth data; not validated on astronauts.
