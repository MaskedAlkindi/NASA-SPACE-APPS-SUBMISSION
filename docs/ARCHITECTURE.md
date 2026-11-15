# Architecture

```mermaid
flowchart LR
  subgraph Clients
    WEB[Website<br/>React + Recharts]
    IOS[iOS app<br/>SwiftUI + HealthKit]
    AND[Android app<br/>Compose + Health Connect]
  end
  subgraph Docker Compose
    NGINX[web: nginx<br/>static + /api proxy]
    subgraph API[api: FastAPI - Python 3.12]
      R[REST /api/v1 + WebSocket /ws/live]
      REG[Module registry]
      subgraph Modules
        AH[apple_health]
        AN[android_health]
        ENV[environment]
        Q[questionnaires]
        SIM[simulation]
        MQSIM[mqtt_sim]
        OSDR[nasa_osdr]
        HRP[nasa_hrp]
        EX[exercise]
      end
      ING[Ingestion + normalised schema]
      INT[Intelligence<br/>daily aggregation · baselines · domains · alerts]
      ML[ML inference<br/>anomaly · fatigue · forecast]
      RES[Research store + TF-IDF retrieval]
      AS[Assistant<br/>context builder · safety · budgets]
    end
    DB[(PostgreSQL)]
    VOL[(nasa_cache volume)]
  end
  NASA[(NASA OSDR public API)]
  OAI[(OpenAI API - optional)]
  RECMODEL[(Exercise recommendation model - optional)]
  POSE[Desktop pose service - optional]

  WEB --> NGINX --> R
  IOS --> R
  AND --> R
  R --> REG --> Modules
  AH & AN & ENV & Q & SIM & MQSIM --> ING --> DB
  EX --> ING
  ING --> INT --> ML
  INT --> DB
  OSDR --> NASA
  OSDR --> VOL
  OSDR --> RES --> DB
  AS --> INT & ML & RES
  AS -. structured summary only .-> OAI
  EX -. contract 1.0.0 .-> RECMODEL
  WEB -. landmarks stay on device .-> EX
  EX -.->|explicit consent| POSE
```

## Module contract

Every integration subclasses `backend/app/modules/base.py::HealthModule`:

| Member | Purpose |
|---|---|
| `module_id`, `version`, `name`, `category` | Identity (`device`, `environment`, `questionnaire`, `simulation`, `research`) |
| `supported_metrics` | Canonical metrics it may emit (validated) |
| `data_class` | Default classification: `real`, `research`, or `simulated` |
| `default_config()` / `public_config()` | Configuration (secrets are never exposed) |
| `map_record(raw)` | Source format → canonical fields (for example HealthKit identifier → `heart_rate`) |
| `validate(raw)` → `NormalizedMeasurement` | Unit, plausible range, astronaut scope, metric support |
| `ingest(records)` → `(items, errors)` | Batch conversion; one bad record never rejects the batch |
| `status()` | Health reporting (`connected`, `available`, `waiting`, `degraded`, `unavailable`, `running`) |

Modules never import each other. `modules/registry.py` loads each one inside `try/except`, and `HMT_DISABLED_MODULES` can switch modules off. The app keeps working when any module is missing (covered by a test). Modules don't access the database directly: persistence, alerting and research storage live in `intelligence/`.

**Adding a device or sensor:** create `modules/<name>/module.py` with a `HealthModule` subclass and add one line to `MODULE_SPECS`. **Adding a model:** add inference to `ml/models/`, training to `ml/training/`, register the artifact version in `ml/models/artifacts.py`, and expose it in `intelligence/models_service.py`. **Adding an exercise:** see [EXERCISE.md](EXERCISE.md). The exercise package keeps its own tables and a versioned HTTP contract, and it emits `exercise_minutes` through the normal ingest path.

## Normalised measurement schema

`backend/app/schemas/measurement.py`:

```
astronaut_id | metric | value (float) | value_json (structured) | unit | timestamp (UTC)
source_device | source_module | quality (good/fair/poor/unknown) | data_class (real/research/simulated) | external_id
```

The metric catalog (`schemas/metrics.py`) fixes each metric's unit, plausible range, domain and daily aggregation rule. `external_id` makes mobile uploads idempotent: re-uploading a day's step total updates it instead of duplicating it.

## Data flow

1. A client posts a batch to `POST /api/v1/measurements` (optionally `module=apple_health`, etc.). The module adapter validates it and access control is applied.
2. `intelligence/ingest.py` stores the readings (upserting on `external_id`), then re-evaluates alerts for the affected astronauts and the habitat environment.
3. `intelligence/daily.py` pivots raw data to one row per day using each metric's aggregation rule. If no device resting HR exists, resting HR falls back to the 5th percentile of heart rate.
4. `intelligence/alerts.py` applies the ML anomaly model plus threshold rules against each astronaut's own robust baseline. Each alert stores its evidence (metric, value, baseline, z-score) and a recommendation, and is deduplicated per rule per day.
5. New measurements and alerts are pushed over `/api/v1/ws/live`, filtered per user.

## Health domains

`intelligence/domains.py` contains independent analysers for **cardiovascular**, **sleep & fatigue** (sleep debt, timing variability as a circadian-disruption indicator), **activity** (training adherence), **wellbeing**, and **environment**. Each is a pure function of the daily frame, so it can be tested and replaced on its own.

## Security and privacy

- PBKDF2 passcodes and HMAC-signed, expiring bearer tokens (stdlib only).
- Roles: `astronaut` (own data only), `flight_surgeon` (read all crew), `mission_control` (read all, run the simulator, post environment data).
- Requests for another astronaut's data return **404** so IDs can't be enumerated. Astronauts can't post data for others or post "simulated" data (covered by tests).
- The WebSocket authenticates on its first message, so no token appears in the URL, and events are filtered per user.
- The assistant sends only the callsign (never the name) and aggregated daily summaries, never raw time series (covered by a test).
- Prototype limitations: there is no TLS inside Docker (put a reverse proxy with HTTPS in front for any non-local use), and rate limits are in-memory for a single process.

## API (v1)

Full interactive docs are at `http://localhost:8000/docs`.

```
GET  /api/v1/health                         POST /api/v1/auth/login        GET /api/v1/auth/me
GET  /api/v1/modules                        GET  /api/v1/questionnaires
GET  /api/v1/mission                        GET  /api/v1/astronauts
GET  /api/v1/astronauts/{id}/summary        GET  /api/v1/astronauts/{id}/measurements?metric=&days=&resolution=raw|daily
POST /api/v1/measurements                   GET  /api/v1/environment
GET  /api/v1/astronauts/{id}/alerts         POST /api/v1/alerts/{id}/acknowledge
GET  /api/v1/astronauts/{id}/predictions    GET  /api/v1/models
POST /api/v1/assistant/chat                 GET  /api/v1/assistant/status
GET  /api/v1/research/datasets              GET  /api/v1/research/findings
GET  /api/v1/research/datasets/{acc}/observations   GET /api/v1/research/search?q=   POST /api/v1/research/import
GET  /api/v1/simulation/scenarios           GET  /api/v1/simulation/status
POST /api/v1/simulation/start               POST /api/v1/simulation/stop   POST /api/v1/simulation/reset
WS   /api/v1/ws/live

Exercise (`/api/v1/exercise`, contract 1.0.0): catalog, programs, tracking spec, per-astronaut profile, goals, sessions, progress, calendar, recommendations, health context, and summary. Landmark and frame inference routes never store video. Details are in [EXERCISE.md](EXERCISE.md).
```

## Docker

| Service | Image | Notes |
|---|---|---|
| `db` | postgres:16-alpine | `pgdata` volume, `pg_isready` health check, not exposed to the host |
| `api` | backend/Dockerfile (python:3.12-slim) | Trains model artifacts **at build time**; waits for the DB; creates tables (idempotent `create_all`) and seeds the demo on start; HTTP health check; non-root user; `nasa_cache` volume |
| `web` | web/Dockerfile (node build → nginx) | Proxies `/api` (including WebSockets) to `api`; starts only after `api` is healthy |

All services use `restart: unless-stopped`, CPU and memory limits, and rotated JSON logs (`docker compose logs -f api`).
