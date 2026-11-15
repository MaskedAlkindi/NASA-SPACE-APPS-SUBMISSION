# Exercise module integration

The exercise module is developed separately (`backend/app/exercise/`, `/api/v1/exercise`). The AI engine does
**not** modify it. Both sides talk through versioned contracts whose JSON Schemas live in `contracts/`.

## AI → exercise: `exercise_guidance.v1`

`GET /api/v1/ai/astronauts/{id}/exercise-guidance`

| Field | Meaning |
|---|---|
| `readiness` | `proceed`, `reduce_intensity`, `rest_and_recheck`, or `insufficient_data` (abstains) |
| `recommendation`, `rationale[]` | Plain text and the reasons |
| `fatigue`, `sleep` | Latest fatigue and sleep/HRV assessment summaries (model, score, evidence level) |
| `anomalies[]` | Physiological anomaly / illness assessments at caution or above |
| `active_alerts[]` | Health alerts relevant to exercise (warning/caution in cardiovascular, vitals, fatigue, sleep, illness, anomaly) |
| `adherence_14d` | From exercise sessions if present, otherwise from daily exercise minutes |
| `source_models`, `limitations`, `not_medical_advice` | Provenance and caveats |

The current logic (`ai/adapters/exercise.recommend`) is deliberately conservative:
- any warning → rest and re-check;
- any caution anomaly or alert → reduce intensity;
- otherwise it follows the fatigue estimate;
- with no fatigue estimate and no alerts, it **abstains**.

## Exercise → AI: `exercise_session_summary.v1`

Either:
- `POST /api/v1/ai/exercise/session-summaries` with `{"sessions": [...]}` (idempotent on `session_id`), or
- nothing at all. The backend data view also reads the exercise module's `workout_sessions` table **read-only** if present, and maps rows to this contract.

Fields:
- session_id, astronaut_id
- started_at, ended_at
- activity_type, planned, completed
- duration_min, intensity_rpe (0–10), avg/max heart rate
- training_load
- goal_id, goal_progress_pct
- source_module, data_class

## Replacing the rules with an exercise AI model

Register a plug-in with `category: "exercise"` whose `Assessment.outputs` contains the `exercise_guidance.v1` fields.
The guidance endpoint can then prefer it over the rules adapter. The contract stays the same, so the exercise module
needs no change.

## Versioning

Additive fields can be added within a version. Breaking changes need a new suffix (`.v2`), with both versions served
until both modules have moved. Tests: `test_exercise_contracts` (engine) and `test_exercise_contracts` (API).
