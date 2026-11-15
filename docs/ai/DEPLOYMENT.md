# Setup and deployment (AI engine)

## Docker (server-side inference, default)

```bash
docker compose up -d --build
```

The API image copies `ai/` (code, manifests, the small trained artifacts and reports) and `contracts/`. Datasets are not
copied (`data/external` is in `.dockerignore`). No training happens at start-up for the new models. The original
`ml/` models are still trained during the image build.

| Variable | Default | Effect |
|---|---|---|
| `HMT_AI_ENABLED` | `true` | `false` turns the engine off (original ml/ path keeps working) |
| `HMT_AI_ON_INGEST` | `true` | Run enabled models in the background when daily summary metrics arrive |
| `HMT_AI_INGEST_DELAY_S` | `30` | Quiet period before a queued run; bursts of uploads for one astronaut are merged into one run |
| `HMT_AI_INGEST_MAX_WAIT_S` | `120` | Upper bound on that wait, so a continuous data stream still gets assessed |
| `HMT_AI_MODEL_PATHS` | empty | Extra folders with plug-ins (mounted volume, for example) |

## Local desktop inference

The engine has no web dependency. It can run models directly from Python:

```python
from ai.registry.registry import ModelRegistry
from ai.core.data import FrameHealthDataView
reg = ModelRegistry()                       # discovers ai/models/*
view = FrameHealthDataView("AST-001", daily_dataframe, units={"resting_heart_rate": "bpm", ...})
print([a.model_dump() for a in reg.run_all(view)])
```

## Device-side and remote providers

Each manifest declares `execution.environments`. `illness_rhr` and `sleep_hrv` are rules over numpy and pandas, small
enough to port on-device. The scikit-learn models are server/desktop only. `execution.provider` is `local` for all
current models; a future HTTP provider can be added in `ai/inference/` and selected per manifest without touching the core.

## Status monitoring

- `GET /api/v1/ai/models` reports per-model `health` (loaded, artifact present, last error), `load_error`, enabled state and invalid manifests.
- Models load lazily and are unloaded when disabled, so not every model needs to be in memory.
- Failures, timeouts and import errors are logged (`hmt.ai.*`) and returned as `status: "error"` assessments.
