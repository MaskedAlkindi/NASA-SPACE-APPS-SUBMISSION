# AI models

> **New:** the plug-in AI engine with models trained or evaluated on real Earth-based research datasets is documented in [ai/README.md](ai/README.md). The simulated models below are still available as `legacy_*` plug-ins.

All three models run **locally inside the backend**. They don't call OpenAI and work offline. Training (`ml/training/`) is separate from inference (`ml/models/`). Artifacts are versioned files in `ml/artifacts/`, rebuilt reproducibly with fixed seeds by `python -m ml.training.train_all`. The Docker build runs this automatically.

> **All metrics below are measured on simulated data. They demonstrate that the pipeline works; they are NOT real-world or clinical accuracy.**

## Training and evaluation protocol

- **Data:** synthetic population from `ml/datasets/synthetic.py`, 60 days per person, with random behaviour episodes and labelled cardio or illness-like anomalies.
- **No leakage:** the split is **by astronaut**. 48 training individuals and 16 held-out test individuals with a different seed, so no person appears in both sets.
- **Personal baselines** for any day use only *earlier* days (a 21-day window ending 2 days before the scored day).
- `ml/artifacts/metrics_report.json` contains the full metrics, the scikit-learn version and the definitions.

> Metrics regenerated on 2026-11-14 after the synthetic generator gained body temperature, glucose and body mass.

## Model 1: personalised anomaly detection (`anomaly-iforest-1.0.0`)

| | |
|---|---|
| Inputs | `resting_heart_rate`, `hrv_sdnn`, `sleep_duration`, `steps` (daily) |
| Personalisation | Each value becomes a robust z-score against the astronaut's **own** baseline: median and scaled MAD over 21 days, excluding the last 2 days, with a minimum scale per metric |
| Model | `IsolationForest` (300 trees), fitted on nominal days' z-vectors |
| Threshold | 97.5th percentile of anomaly scores on nominal training days |
| Output | Score, percentile against nominal training days, flag, ranked contributors (value, baseline median, usual 10–90% range, z, direction), missing inputs, reliability, model version |
| Missing data | Missing metrics are treated as "at baseline" and reported. Fewer than 2 metrics with a baseline returns `insufficient_baseline` |

| Held-out simulated test (816 days, 30 anomalous) | ROC-AUC | Precision | Recall | FPR |
|---|---|---|---|---|
| Isolation Forest | 0.994 | 0.58 | 0.93 | 0.025 |
| Rule baseline (\|z\| resting HR > 2.5) | 1.000 | 0.73 | 1.00 | 0.014 |

**Honest reading:** the injected synthetic anomalies are dominated by a resting-HR rise, so a single-metric rule does better than the forest on this test set (higher precision, lower false-positive rate). The forest's value is flagging unusual *combinations* (for example an HRV drop plus short sleep with normal HR) that a single rule misses. The tool runs both: rules for transparency, the model for multivariate patterns.

## Model 2: fatigue estimation (`fatigue-hgb-1.0.0`), SIMULATION MODEL

| | |
|---|---|
| Target | Samn-Perelli fatigue score 1–7 reported that day (**synthetic labels**) |
| Features | `sleep_last`, `sleep_debt_3d` (vs a fixed 7.5 h reference), `sleep_midpoint_sd_3d`, `sleep_efficiency_last`, `exercise_prev`, `workload_today` (NASA-TLX), `fatigue_prev` |
| Model | `HistGradientBoostingRegressor` (handles missing values natively; 8% of training features are randomly removed so it learns to cope) |
| Uncertainty | 80% interval from held-out residual quantiles |

| Held-out simulated test (960 days) | MAE | RMSE | R² |
|---|---|---|---|
| Model | 0.52 | 0.67 | 0.61 |
| Persistence (yesterday's score) | 0.71 | 0.92 | 0.25 |
| Mean | 0.84 | 1.07 | 0.00 |

No public dataset provides astronaut fatigue labels together with wearable data, so this model is explicitly a **simulation model**. Real use would require labelled check-in data, for example from the HEALTH-01 questionnaire module.

## Model 3: trend forecasting (`forecast-holt-1.0.0`)

| | |
|---|---|
| Method | Damped Holt linear exponential smoothing, refit on each astronaut's own series (last 45 days) |
| Parameters | α, β, φ selected by rolling-origin backtest on the training population (grid search) |
| Horizon | 7 days. 80% interval = 1.28 × backtest 1-step residual SD × √h (an approximation, documented as such) |
| Output | Points with lower and upper 80% bounds, recent 7-day mean, projected change, trend direction (stable unless the change exceeds 1 residual SD) |
| Minimum data | 10 days, otherwise `insufficient_data` |

| 7-day MAE on held-out simulated individuals | Model | Naive (last value) | Mean of last 7 days |
|---|---|---|---|
| Resting HR (bpm) | 1.86 | 2.50 | 2.18 |
| Sleep duration (h) | 0.44 | 0.60 | 0.48 |
| HRV SDNN (ms) | 4.06 | 5.49 | 4.72 |

The selected α ≈ 0.05 means a heavily smoothed level. That's appropriate for noisy daily physiology, but it reacts slowly to genuine sudden changes, which the anomaly detector covers.

## Alert rules (transparent, configurable demo thresholds)

The following rules are in `backend/app/intelligence/alerts.py`:

- resting HR z ≥ 2.5 **and** at least 8 bpm above baseline
- HRV z ≤ −2.5
- SpO₂ < 92%
- systolic BP ≥ 140
- 3-night mean sleep < 6 h, or last night < 5 h
- sleep-midpoint SD > 1.2 h over 5 nights
- self-reported fatigue ≥ 6 (warning), or model estimate ≥ 5
- 3-day exercise < 50% of usual
- mood ≤ 2 with stress ≥ 8
- reaction time z ≥ 2.5
- environment: CO₂ caution 3 / warning 4 mmHg, temperature, humidity, pressure, and dose-rate ranges

The thresholds are **demo values**, not flight rules. Configure them to NASA-STD-3001 and mission flight rules for real use.

## Health assistant (OpenAI, local Ollama, or offline)

**Choosing a provider.** The assistant supports three interchangeable providers (`backend/app/assistant/providers.py`):

| Provider | Where it runs | Models offered |
|---|---|---|
| `openai` | OpenAI cloud (needs `OPENAI_API_KEY`) | `OPENAI_MODEL` plus `OPENAI_MODEL_OPTIONS` |
| `ollama` | **Locally**, via Ollama on the host; health context never leaves the machine | Every installed Ollama **chat** model, discovered live from `/api/tags`; embedding-only models are hidden |
| `offline` | Inside the API | Deterministic explainer (no LLM) |

Selection order:
1. The provider/model picked in the website's **Model** dropdown, which applies to that request only.
2. The default saved from the website. Mission control or the flight surgeon pick a model and click **Save as default** (`PUT /api/v1/assistant/settings`); it's stored in the `app_settings` table.
3. `ASSISTANT_PROVIDER` in `.env`. The default `auto` uses OpenAI if a key is set, else a local Ollama model if one is running, else the offline explainer.

Every provider gets the same grounded context, system prompt, grounding check and disclaimer. If the chosen provider fails, times out or is unavailable, the offline explainer answers and the response says why. `GET /api/v1/assistant/status` lists the providers, their availability and models, and the active selection.

**Local model note:** tested live with `qwen2.5:7b` (Ollama 0.20.7 on the Docker host): about 26 s per answer on this machine, using about 1,700 prompt tokens. Its observations matched the dashboard, but small local models can produce weaker reasoning than cloud models (one answer linked *higher* HRV to fatigue). Keep the "estimates, not diagnoses" framing, and prefer larger local models if your hardware allows.

### Pipeline details

`backend/app/assistant/`

1. **Context builder** (`context.py`) detects intents (cardio, sleep, activity, wellbeing, environment, alert, next steps, research, overview). It then collects only the relevant domain summaries, the last 3 days of alerts with their evidence, model outputs, environment data (only if relevant), and at most N NASA research passages, retrieved by TF-IDF over the curated HRP summaries, computed Inspiration4 findings and dataset descriptions. It sends the callsign only, never the real name or raw time series.
2. **LLM call** (`providers.py`): Ollama uses `/api/chat` (non-streaming, `num_ctx` 8192, temperature 0.2, `OLLAMA_TIMEOUT_S`). OpenAI uses Chat Completions with the configurable `OPENAI_MODEL` (default `gpt-5-mini`). `reasoning_effort` is sent only to reasoning models and retried without it if rejected. It applies `max_completion_tokens`, a timeout, and at most 1 retry.
3. **Safety and grounding:** the system prompt forbids invented numbers, diagnoses and treatment instructions, separates observations from estimates, and requires escalation for warnings or severe symptoms. A post-check flags any number in the answer that doesn't appear in the context. An escalation line is forced if severe symptoms were mentioned. A disclaimer is always appended.
4. **Cost controls:** cheap model, max output tokens, last 6 history turns, 3 passages, 25 s timeout, a per-user rate limit (6/min), and global daily request and token budgets tracked in the `assistant_usage` table.
5. **Offline fallback** (`fallback.py`) is a deterministic, template-based explainer over the same context. It's used when no provider is available or chosen, the budget or rate limit is exhausted, or the provider fails or times out. OpenAI budgets don't apply to local Ollama calls; the per-user rate limit does. It can only restate values that are in the context.

## Exercise recommendations (separate contract)

Exercise suggestions are not one of the three models above. They live in `backend/app/exercise/recommendations.py`. With `EXERCISE_RECOMMENDER_URL` empty, a transparent rules engine answers. A future model can POST to that URL using contract `1.0.0` (`GET /api/v1/exercise/contracts`). Local health flags (high fatigue, very short sleep, low SpO2, open warnings) force human review even if the remote model disagrees. The shape, fallback, and limits are documented in [EXERCISE.md](EXERCISE.md). This section is additive: it does not change the anomaly, fatigue, or forecast models.
