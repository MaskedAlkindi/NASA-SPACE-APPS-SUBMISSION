# Health data integration

Models never touch the database. They read a `HealthDataView` (`ai/core/data.py`) for exactly one astronaut:

| Method | Returns |
|---|---|
| `daily(metrics, days)` | One row per day (`date` + one column per canonical metric), aggregated with each metric's catalog rule; NaN where missing |
| `series(metric, days)` | Raw samples: `timestamp`, `value`, `value_json` |
| `last_seen(metric)` | Newest sample time, used for staleness checks |
| `unit(metric)` | Canonical unit from the metric catalog |
| `profile()` | Non-identifying context (role, data class); never names |
| `exercise_sessions(days)` | `exercise_session_summary.v1` dicts |

The backend implementation is `backend/app/ai_engine/data_view.py`.

## Supported measurements

Units come from `backend/app/schemas/metrics.py`; every stored measurement also carries timestamp, source device, source module, quality and data class (real / research / simulated).

| Area | Canonical metrics |
|---|---|
| Heart | `heart_rate`, `resting_heart_rate` (bpm); `hrv_sdnn`, `hrv_rmssd` (ms; never mixed) |
| Blood pressure | `blood_pressure_systolic`, `blood_pressure_diastolic` (mmHg) |
| Sleep | `sleep_duration` (h), `sleep_efficiency` (%), `sleep_midpoint` (h) |
| Activity / exercise | `steps`, `exercise_minutes`; exercise sessions via the contract or the exercise module's table |
| Glucose / metabolic | `blood_glucose` (mg/dL), `fasting_insulin` (µIU/mL, lab), `body_mass` (kg) |
| Self-reports | `fatigue_score` (Samn-Perelli 1–7), `stress_score`, `mood_score`, `workload_tlx` |
| Baselines | Computed per model from the astronaut's own history, causally (`ai/preprocessing/signals.causal_baseline`) |

## Data quality rules

Every model's declared inputs are checked before it runs:
- **Missing:** a required metric has no samples → `insufficient_data`, listing the missing metric.
- **Incompatible units:** the catalog unit differs from the model's declared unit → `insufficient_data` with the mismatch. There is no silent conversion.
- **Stale:** the newest sample is older than `max_staleness_days`, counted from the astronaut's latest data → `insufficient_data`.
- **Irregular sampling:** daily views keep calendar gaps explicit (`asfreq("D")`), and models require minimum history (`min_days`).
- **No substitution:** nothing is imputed with simulated values. Simulated demo data is only present because it was stored as simulated, and it keeps that label.
- **Profile isolation:** a view is built per astronaut ID, and API access control is applied before a view is built (tests: `test_profile_isolation`, `test_views_are_per_astronaut`).
