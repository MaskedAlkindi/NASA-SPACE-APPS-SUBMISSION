# HEALTH-01: quick guide (demo / MVP)

Everything you need to run and show the demo. This is a demo build: the passcodes below are shared demo values, not real secrets. Change them before any real use.

## 1. Start and stop

```bash
cp .env.example .env
```

```bash
docker compose up -d --build
```

| Action | Command |
|---|---|
| See status | `docker compose ps` |
| Follow API logs | `docker compose logs -f api` |
| Stop (keep data) | `docker compose down` |
| Stop and wipe all data | `docker compose down -v` |
| Check everything works | `./scripts/smoke_test.sh` |
| Run the test suite | `./scripts/test.sh` |
| Simulated MQTT sensors (own command) | `.\scripts\mqtt_sim.ps1` |

The first build takes a few minutes, because it trains the AI models.

## 2. Addresses

| What | URL |
|---|---|
| Landing page | http://localhost:8080 |
| Demo (website) | http://localhost:8080/app |
| Serious edition (if started) | http://localhost:9080 |
| Fine-tuning trainer (if started) | http://localhost:8600/health |
| API | http://localhost:8000 |
| API docs (try every endpoint) | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/v1/health |
| Database | Not exposed outside Docker |

## 3. Logins

All accounts use the same passcode: **`hmt-demo`** (set by `DEMO_PASSCODE` in `.env`).

| Username | Role | What they can do |
|---|---|---|
| `mission-control` | Mission control (admin) | Everything, plus the **Crew** page: edit astronauts, reset their passcodes, add extra Mission Control passcodes. **Use this for the demo.** |
| `flight-surgeon` | Flight surgeon | See the whole crew, set the default assistant model |
| `hajid` | Hajid Alkindi, AST-001 (simulated data) | Sees only his own data |
| `osama` | Osama Al Adawani, AST-002 (simulated data) | Sleep and fatigue story |
| `hamood` | Hamood Almahrouqi, AST-003 (simulated data) | Sees only his own data |
| `haitham` | Al Haitham Al Obaidani, AST-004 (simulated data) | Heart-rate anomaly story |
| `mohmmed` | Mohmmed Alwahabi, AST-005 (simulated data) | Sees only his own data |
| `pilot` | Astronaut, AST-900 (real device) | Empty account for uploading your own phone health data |

To change the passcode, edit `DEMO_PASSCODE` in `.env` and wipe the data (`docker compose down -v`), then start again. Existing accounts keep the passcode they were created with.

## 4. Other settings in `.env`

| Setting | Demo value | Meaning |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `hmt` / `hmt-local-only` / `hmt` | Database login, only used inside Docker |
| `SECRET_KEY` | `change-me-to-a-long-random-string` | Signs login tokens. Change it for anything beyond a demo |
| `DEMO_MODE` | `true` | Creates the simulated crew and shows demo accounts on the login page |
| `SEED_DAYS` | `45` | Days of simulated history created on first start |
| `ASSISTANT_PROVIDER` | `auto` | `auto`, `openai`, `ollama` or `offline` |
| `OPENAI_API_KEY` | empty | Optional. Add a key to enable OpenAI models |
| `OLLAMA_MODEL` | empty | Optional. Empty means the first installed chat model (here `qwen2.5:7b`) |
| `NASA_ONLINE` | `true` | `false` = use only the bundled NASA files (fully offline) |
| `SIM_TICK_SECONDS` | `1.5` | Real seconds per simulated hour in the simulator |
| `WEB_PORT` / `API_PORT` | `8080` / `8000` | Ports on your computer |

## 5. Phone apps

| Where the app runs | Server address to type in the app |
|---|---|
| Android emulator | `http://10.0.2.2:8000` |
| iPhone Simulator on the Mac running Docker | `http://localhost:8000` |
| Real phone on the same Wi-Fi | `http://<computer's IP>:8000` (find it with `ipconfig`) |

- Log in as `pilot` to upload your own health data, or `hajid` to browse simulated data.
- **Android:** `cd android` then `./gradlew assembleDebug` (needs JDK 17). The APK lands in `android/app/build/outputs/apk/debug/`.
- **iPhone:** open `ios/HealthMonitor/HealthMonitor.xcodeproj` in Xcode 16 on a Mac, pick your signing team, then Run.

## 6. Assistant models

- Choose per question from the **Model** dropdown on the AI Assistant page.
- To make a choice the default for everyone, sign in as `mission-control` and click **Save as default**.
- Local Ollama models are found automatically if Ollama is running. Install another with `ollama pull <model>`; it appears within about 15 seconds.
- With no OpenAI key and no Ollama, the offline explainer answers.

## 7. Demo checklist

1. Before presenting: Simulator → **Reset demo data**. Earlier simulator runs add future-dated readings.
2. Sign in as `mission-control`.
3. Show Mission Overview, then Dashboard → **HAITHAM** (heart) and **OSAMA** (sleep).
4. AI Intelligence → HAITHAM: flagged days and the reasons.
5. Simulator: `cardio_anomaly` on HAJID, 4 days, 0.3 s per sim-hour. Watch the alerts appear.
6. AI Assistant → OSAMA: "Has my sleep been getting worse?"
7. NASA Research: pick WHITE BLOOD CELL COUNT in the lab explorer.

The full script is in [docs/DEMO.md](docs/DEMO.md).

## Exercise module

Open **Exercise & Fitness** on the website after signing in. Demo crew members already have example programs and a few seeded sessions. Log a workout on the **Log** tab, or open **Camera** for squat, lunge, and arm-raise counting. Programs are examples, not prescriptions. Setup for the optional pose service and recommendation model is in [docs/EXERCISE.md](docs/EXERCISE.md).

## 8. If something goes wrong

| Problem | Fix |
|---|---|
| Website says "Invalid credentials" | Use passcode `hmt-demo`. If you changed `DEMO_PASSCODE`, wipe the data (`docker compose down -v`) and start again |
| Logged out after a restart | Expected while `SECRET_KEY` is the default. Sign in again |
| Port already in use | Change `WEB_PORT` / `API_PORT` in `.env` |
| Assistant says "offline explainer" | No OpenAI key and Ollama not running. Start Ollama, or add a key |
| Docker stops responding while the Android emulator runs | Close the emulator, or give Docker Desktop more memory |
| Old `batman_*` volumes in Docker Desktop | Leftovers from before the rename. Remove with `docker volume rm batman_pgdata batman_nasa_cache` |

## 9. Renaming the product

"HEALTH-01" is a working name. The README's **Renaming the product** section lists the four places to change it. After replacing the logo in `LOGO CUSTOM/`, run `python scripts/make_logo_assets.py`.
