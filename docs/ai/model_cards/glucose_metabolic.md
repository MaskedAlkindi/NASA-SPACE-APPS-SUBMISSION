# Model card: Glucose & metabolic monitoring (CGMacros)

| | |
|---|---|
| ID / version | `glucose_metabolic` v1.0.0 |
| Category | glucose |
| Status | ready |
| Enabled by default | True |
| Evidence level | Earth-based research data (not astronauts) |
| Validated on astronaut data | **no** |
| Execution | server, desktop; provider local; timeout 10.0 s |

**What it does.** Fasting glucose trend and variability, HOMA-IR when fasting insulin is measured, and (with CGM data) CGM metrics plus a research insulin-resistance pattern flag.

**Intended use.** Track metabolic trends in flight and suggest when a lab check could be worthwhile.

**Not intended for.** Diagnosing diabetes or insulin resistance; replacing laboratory testing.

## Dataset(s)
- **CGMacros v1.0.0** - https://physionet.org/content/cgmacros/1.0.0/  
  Licence: CC BY-NC-SA 4.0. Population: 45 adults: normal, prediabetes, type 2 diabetes (USA). Citation: CGMacros (PhysioNet 2025); Goldberger A. et al. PhysioNet. Circulation 2000

## Inputs
| Metric | Unit | Required | Min days | Max staleness (days) |
|---|---|---|---|---|
| blood_glucose | mg/dL | True | 3 | 3.0 |
| fasting_insulin | µIU/mL | False | 1 | 30.0 |

## Outputs
- `fasting_mean_14d`: mg/dL
- `fasting_sd_14d`: mg/dL
- `days_outside_reference_14d`: count
- `trend_mg_dl_per_week`: mg/dL/week
- `homa_ir`: unitless, if insulin measured
- `cgm`: CGM consensus metrics, if dense data
- `p_insulin_resistance_pattern`: probability, if CGM

## Training / evaluation method and actual metrics
Participants: 45 (prediabetes: 16, normal: 15, diabetes: 14, from HbA1c).
HOMA-IR (fasting glucose [mg/dL] x fasting insulin [uU/mL] / 405 (Matthews 1985)): median 4.24 (IQR [2.25, 5.08]); by group {'diabetes': 5.06, 'normal': 1.99, 'prediabetes': 4.61}. HOMA-IR cut-offs vary by population (commonly 2.0-2.9); 2.5 used here for illustration.
Insulin-resistance flag from CGM metrics (HOMA-IR >= 2.5, 32/45 positive): leave-one-subject-out AUC **0.825** (bootstrap 95% CI [0.679, 0.949]). Spearman with HOMA-IR: {'mean_mg_dl': 0.527, 'sd_mg_dl': 0.447, 'cv_pct': 0.096, 'tir_70_180_pct': 0.155, 'tar_180_pct': 0.471, 'night_mean_mg_dl': 0.61}.
Post-meal glucose rise (1696 meals, 45 people, leave-one-subject-out): MAE **18.6 mg/dL** vs 26.6 (carbs-only linear) and 27.3 (predict mean); Spearman 0.668.

## Alerting
Emits alerts: True; concern at severity >= caution; cooldown 72.0 h; thresholds {'homa_ir_info': 2.5, 'ir_probability_info': 0.8}.

## Limitations
- 45 adults, ~10 days each; Earth-based, not astronauts.
- CGM-based insulin-resistance flag is a research signal, not a validated alternative to fasting insulin / HOMA-IR or clamp testing.
- The app's astronauts have daily fasting glucose, not CGM or meal logs, so the CGM parts run only if CGM data is supplied.
