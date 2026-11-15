# AI inference API (`/api/v1/ai`)

Bearer-token auth as for the rest of the API. Astronaut accounts can only reach their own astronaut ID; other IDs
return **404**. Interactive docs: `http://localhost:8000/docs` (tag *ai engine*).

| Method & path | Who | Purpose |
|---|---|---|
| `GET /ai/models` | any user | All registered models: manifest, enabled state, thresholds, health, evaluation report, invalid manifests |
| `GET /ai/models/{id}` | any user | One model |
| `PUT /ai/models/{id}` `{"enabled": bool, "thresholds": {...}}` | mission control / flight surgeon | Enable/disable; override declared thresholds only (others → 422) |
| `POST /ai/astronauts/{id}/run[?model_id=a&model_id=b]` | self or crew-wide | Run enabled models now; stores assessments; returns `alerts_created` |
| `GET /ai/astronauts/{id}/assessments[?refresh=true]` | self or crew-wide | Latest assessment per model (runs once if none stored) |
| `GET /ai/astronauts/{id}/exercise-guidance` | self or crew-wide | `exercise_guidance.v1` for the exercise module |
| `POST /ai/exercise/session-summaries` `{"sessions": [exercise_session_summary.v1...]}` | self or crew-wide | Exercise module reports sessions (idempotent on `session_id`) |
| `GET /ai/contracts` | any user | JSON Schemas of the shared contracts |

## Assessment (`ai_assessment.v1`, see `contracts/ai_assessment.v1.json`)

```json
{
  "astronaut_id": "AST-004", "model_id": "illness_rhr", "model_version": "1.0.0",
  "assessed_at": "...", "data_as_of": "2026-11-14", "status": "ok",
  "category": "illness", "severity": "caution", "score": 8.23, "score_label": "well above usual",
  "scale": "robust z vs own 28-day baseline", "uncertainty": {}, "calibration": "Stanford ... held-out sensitivity 0.792 ...",
  "explanation": "Resting heart rate 80 bpm vs your usual 65 bpm (z = 8.2).",
  "contributing": [{"metric": "resting_heart_rate", "value": 80, "unit": "bpm", "baseline": 65, "deviation": 8.23}],
  "recommendation": "...", "data_quality": {"coverage": 1.0, "missing": [], "stale": []},
  "limitations": ["Earth-based evaluation ..."], "evidence_level": "earth_research", "outputs": {"z": 8.23}
}
```

`status`:
- `ok`
- `insufficient_data`: inputs missing, stale, wrong unit, or too little history
- `abstained`
- `error`: model failed or timed out; the app is unaffected
- `disabled`

`severity`: `none` < `info` < `caution` < `warning`. Results at or above a model's `alerting.min_severity` are *concerns*; lower results are *insights*.
