# Model registry and how to add a model

## Discovery

`ai.registry.registry.ModelRegistry` scans every `manifest.json` one level below:

1. `ai/models/`
2. every folder listed in the `HMT_AI_MODEL_PATHS` environment variable (separated by `;` on Windows, `:` elsewhere)

Each manifest is validated (`ai.core.types.ModelManifest`). Invalid or duplicate manifests are skipped and listed in
`GET /api/v1/ai/models` → `invalid_manifests`; they never stop the app.

## Lifecycle

- **Lazy loading:** a model's class is imported and its artifacts loaded on first use. `unload()` frees it, and disabling a model unloads it.
- **Isolation:** each prediction runs in a worker thread with the manifest's `execution.timeout_s`. Timeouts, import errors and exceptions become an `Assessment` with `status="error"`, so other models and the app keep running.
- **State:** the enabled flag and threshold overrides are stored per model. The backend uses the `ai_model_state` table; standalone use defaults to in-memory or a JSON file. Change them in the AI Models page or with `PUT /api/v1/ai/models/{id}` (mission control or flight surgeon only).

## The plug-in contract

`manifest.json` declares:

| Field | Meaning |
|---|---|
| `id`, `name`, `version`, `category` | Identity. `category` groups results (illness, fatigue, glucose, sleep_hrv, orthostatic, anomaly, forecast, exercise...) |
| `description`, `intended_use`, `not_intended_for` | Shown on the model card and in the UI |
| `entrypoint` | `"package.module:ClassName"`, a subclass of `ai.core.plugin.ModelPlugin` |
| `inputs[]` | `FeatureSpec`: canonical `metric`, required `unit`, `kind`, `required`, `min_days`, `max_staleness_days` |
| `outputs` | Description of `Assessment.outputs` keys |
| `supported_indicators` | Health indicators covered (blood pressure, heart rate, blood sugar...) |
| `datasets[]` | Name, source, licence, citation, population, `astronaut_data`, `simulated`, provenance file |
| `evidence_level` | `spaceflight` / `earth_research` / `simulation` / `rule_based` |
| `validated_on_astronauts` | Must stay `false` until astronaut validation exists |
| `status` | `ready` / `research_prototype` / `pending_data` / `deprecated` |
| `artifact`, `report` | Paths relative to the model folder |
| `enabled_by_default` | Initial state |
| `execution` | Environments (`server`, `desktop`, `device`), provider, timeout, memory, runtime requirements |
| `alerting` | `emit_alerts`, `min_severity` for a *concern* (lower = insight), `cooldown_hours`, configurable `thresholds` |

The Python class implements:

- `_load()` / `_unload()` (optional): read or free artifacts.
- `_predict(view, quality) -> Assessment`: `view` is a `HealthDataView` for **one** astronaut. `quality` is the result of the automatic input check.

Before `_predict` is called, `ModelPlugin.predict` checks every required input for presence, unit compatibility and staleness. If anything is missing it returns `status="insufficient_data"` with the reason. Models must also return `insufficient_data` or `abstained` themselves when their own needs aren't met. They must never fill in missing values with invented ones.

## Add a new model (5 steps)

1. Copy `ai/documentation/template_model/` to `ai/models/<your_id>/`. For an external plug-in, copy it to any folder and add that folder to `HMT_AI_MODEL_PATHS`.
2. Edit `manifest.json`: set `id`, `entrypoint` (`ai.models.<your_id>.model:YourClass`), inputs with units, datasets with licence, `evidence_level`, `status`, alert policy.
3. Implement `_predict` and return an `Assessment`. Put the trained artifact in `artifacts/` and evaluation results in `report.json`.
4. Restart the API. The model appears in `GET /api/v1/ai/models` and on the AI Models page, disabled if `enabled_by_default` is false.
5. Run `python -m ai.documentation.generate_cards` to create its model card, and add tests to `ai/tests/`.

No core file changes are needed. The test `test_core_has_no_hardcoded_model_references` enforces this.

Category `exercise`: a dedicated exercise AI model can replace the rule-based exercise adapter by returning the same
`exercise_guidance.v1` content in `Assessment.outputs`; see [EXERCISE_INTEGRATION.md](EXERCISE_INTEGRATION.md).
