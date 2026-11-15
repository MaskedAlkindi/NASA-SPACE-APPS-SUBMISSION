# Alerts integration

`ai/adapters/alerts.py` turns an `Assessment` into a standard event (`ai.alert_event.v1`):

| Field | |
|---|---|
| astronaut_id, model_id, model_version, assessed_at, data_as_of | Who / what / when |
| risk_category, severity, kind | `kind` = `concern` if severity ≥ the model's `alerting.min_severity`, else `insight` |
| score, score_label, scale, calibration, uncertainty | With the evaluation it is calibrated against, in words |
| explanation, contributing[] | Measurements that drove the result, with baseline and deviation |
| recommended_follow_up | Conservative next step |
| data_quality, limitations, evidence_level, evidence_note | E.g. "Research model ... not validated on astronauts" |
| not_a_diagnosis | Always `true` |
| dedupe_key | `ai:{model}:{astronaut}:{category}:{severity}:{time bucket}` (bucket = cooldown window) |

The backend bridge (`backend/app/ai_engine/service.py`):

- **Concerns** are written to the existing `alerts` table:
  - `source` = `ai:<model>@<version>`
  - evidence comes from `contributing`
  - the evidence note is appended to the message
  - de-duplication uses `dedupe_key`, so the same finding is notified once per cooldown window
- **Insights** are stored only as assessments, shown on the AI Models page and available to the assistant and exercise module. That keeps the alert list for things worth attention.
- **When it runs:**
  - when new daily summary metrics arrive (resting HR, sleep, HRV, glucose, insulin, fatigue check-in, exercise minutes): one background run per astronaut after a 30 s quiet period (`HMT_AI_INGEST_DELAY_S`, at most `HMT_AI_INGEST_MAX_WAIT_S` = 120 s), so bursts are merged; ingestion is never blocked;
  - or on demand with `POST /ai/astronauts/{id}/run`.
- **Safeguards:**
  - thresholds are configurable per model (validated against the manifest);
  - research prototypes ship with `emit_alerts: false`;
  - weak models are capped in code (for example `fatigue_pmdata` never exceeds `info`);
  - the original rule-based alerts and the original ML path are unchanged.
- **Switching off:** `HMT_AI_ENABLED=false` disables the engine entirely; `HMT_AI_ON_INGEST=false` keeps it on-demand only.
