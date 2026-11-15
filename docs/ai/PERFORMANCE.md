# Model performance report

Generated from `ai/models/*/report.json` by `python -m ai.documentation.generate_cards`.
All results are from **Earth-based** or **simulated** data. **No model has been validated on astronauts.**

## Fatigue & stress from wearables (PMData) (`fatigue_pmdata`)
Evidence: Earth-based research data (not astronauts). Validated on astronauts: no.

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

## Glucose & metabolic monitoring (CGMacros) (`glucose_metabolic`)
Evidence: Earth-based research data (not astronauts). Validated on astronauts: no.

Participants: 45 (prediabetes: 16, normal: 15, diabetes: 14, from HbA1c).
HOMA-IR (fasting glucose [mg/dL] x fasting insulin [uU/mL] / 405 (Matthews 1985)): median 4.24 (IQR [2.25, 5.08]); by group {'diabetes': 5.06, 'normal': 1.99, 'prediabetes': 4.61}. HOMA-IR cut-offs vary by population (commonly 2.0-2.9); 2.5 used here for illustration.
Insulin-resistance flag from CGM metrics (HOMA-IR >= 2.5, 32/45 positive): leave-one-subject-out AUC **0.825** (bootstrap 95% CI [0.679, 0.949]). Spearman with HOMA-IR: {'mean_mg_dl': 0.527, 'sd_mg_dl': 0.447, 'cv_pct': 0.096, 'tir_70_180_pct': 0.155, 'tar_180_pct': 0.471, 'night_mean_mg_dl': 0.61}.
Post-meal glucose rise (1696 meals, 45 people, leave-one-subject-out): MAE **18.6 mg/dL** vs 26.6 (carbs-only linear) and 27.3 (predict mean); Spearman 0.668.

## Illness-related resting heart rate change (`illness_rhr`)
Evidence: Earth-based research data (not astronauts). Validated on astronauts: no.

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

## Personal anomaly detection (original, simulation-trained) (`legacy_anomaly`)
Evidence: Simulated data only. Validated on astronauts: no.

Simulated evaluation (see docs/AI_MODELS.md): {"roc_auc": 0.9937, "precision": 0.5833, "recall": 0.9333, "false_positive_rate": 0.0254, "n": 816, "n_positive": 30}
Real-data check for legacy_anomaly: see illness_rhr report rows `legacy_iforest`.

## Fatigue estimate (original, simulation model) (`legacy_fatigue_sim`)
Evidence: Simulated data only. Validated on astronauts: no.

Simulated evaluation (see docs/AI_MODELS.md): {"mae": 0.5209, "rmse": 0.6694, "r2": 0.6078, "n": 960}
Real-data check for legacy_anomaly: see illness_rhr report rows `legacy_iforest`.

## 7-day trend forecast (original) (`legacy_forecast`)
Evidence: Simulated data only. Validated on astronauts: no.

Simulated evaluation (see docs/AI_MODELS.md): {"resting_heart_rate": {"params": {"alpha": 0.05, "beta": 0.01, "phi": 0.7}, "residual_sd_h1": 2.654, "backtest": {"mae_model": 1.86, "mae_naive_last_value": 2.4962, "mae_mean_last_7d": 2.1763, "horizon_days": 7}}, "sleep_duration": {"params": {"alpha": 0.05, "beta": 0.01, "phi": 0.5}, "residual_sd_h1": 0.5808, "backtest": {"mae_model": 0.4397, "mae_naive_last_value": 0.6028, "mae_mean_last_7d": 0.4765, "horizon_days": 7}}, "hrv_sdnn": {"params": {"alpha": 0.05, "beta": 0.05, "phi": 0.5}, "residual_sd_h1": 5.2613, "backtest": {"mae_model": 4.0569, "mae_naive_last_value": 5.4885, "mae_mean_last
Real-data check for legacy_anomaly: see illness_rhr report rows `legacy_iforest`.

## Orthostatic response features (research prototype) (`orthostatic`)
Evidence: Earth-based research data (not astronauts). Validated on astronauts: no.

signal-processing verification + descriptive statistics (research prototype). 71/71 recordings processed.
Agreement with the study's published sit-to-stand change (sign-aligned): {'seg_delta_sbp': {'n': 57, 'pearson_r': 0.529, 'mean_abs_diff_mmHg': 11.9, 'window': "whole 5-min segments (study's windows)"}, 'seg_delta_dbp': {'n': 57, 'pearson_r': 0.423, 'mean_abs_diff_mmHg': 6.5, 'window': "whole 5-min segments (study's windows)"}, 'delta_sbp': {'n': 57, 'pearson_r': 0.523, 'mean_abs_diff_mmHg': 11.3, 'window': 'first 3 min after standing (consensus OH window)'}, 'delta_dbp': {'n': 57, 'pearson_r': 0.473, 'mean_abs_diff_mmHg': 6.4, 'window': 'first 3 min after standing (consensus OH window)'}}
Consensus criteria met: {'oh_pct': 4.2, 'hr_rise_ge30_pct': 2.8}. Median changes: {'delta_sbp': 4.1, 'delta_dbp': 4.4, 'delta_hr': 7.9, 'hr_peak_rise': 12.4}.
Association with self-reported orthostatic symptoms (exploratory): {'n': 71, 'with_symptoms': 36, 'auc_sbp_drop': 0.571, 'auc_hr_rise': 0.433}

## Sleep & HRV recovery indicators (`sleep_hrv`)
Evidence: Transparent rules on published reference values. Validated on astronauts: no.

signal-processing verification (no model training).
HR from our RR processing vs ActiGraph HR: 22 people, 29993 minutes, median MAE 1.08 bpm, bias -0.19 bpm, r 0.988.
Sleep efficiency recomputed as TST / time in bed: max difference 0.0 percentage points (21 people).
Night RMSSD median 52.6 ms (IQR [41.2, 59.3]); artefact filter kept 78.8% of beats.
Exploratory correlations (uncorrected): {'night_rmssd_vs_Daily_stress': {'n': 19, 'spearman_rho': -0.27, 'p_value': 0.264}, 'night_rmssd_vs_STAI2': {'n': 19, 'spearman_rho': 0.244, 'p_value': 0.313}}
