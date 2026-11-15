# HEALTH-01 setup walkthrough

Everything runs and stores its data on your own machine unless you choose the online demo.

| What | Where it runs | Address |
|---|---|---|
| Website, notebook look (landing page + demo) | Docker | http://localhost:8080 (demo at `/app`) |
| Website, **serious** edition (password) | Docker, separate deployment | http://localhost:9080 |
| API and its docs | Docker | http://localhost:8000/docs |
| Desktop app (Electron) | Your computer | shows any of the above |
| Phone apps | iPhone / Android | upload to any of the above |
| Local AI models | Ollama on your computer | http://localhost:11434 |
| Fine-tuning trainer | A machine with an NVIDIA GPU | http://localhost:8600 |

## 1. Website and API (notebook edition)

1. Install Docker Desktop.
2. In the repository folder, copy `.env.example` to `.env`. The defaults work for a local demo.
3. Start it:

   ```bash
   docker compose up -d --build
   ```

4. Open http://localhost:8080 for the landing page. Press **Open the demo**. Demo logins and the passcode are in [GUIDE.md](../GUIDE.md).

## 2. The serious edition (separate deployment)

The same sketch UI with less text, behind a site password (`SITE_PASSWORD`, default `staydetermined`). It has its own ports and its own database, so both editions can run side by side.

```bash
docker compose -f deploy/serious/docker-compose.yml --env-file .env up -d --build
```

Open http://localhost:9080. To build the website alone in this look for development, run `VITE_EDITION=serious npm run dev` in `web/`.

## 3. Desktop app (Electron)

```bash
cd desktop
```

```bash
npm install
```

```bash
npm start
```

- **First screen:** choose a server. The list already has *This computer (Docker)*, and you can type any other address, such as a crew server or the online demo. **Start local stack** runs `docker compose up -d` for you.
- **Ctrl+K** switches server at any time. **Ctrl+M** opens *Local AI models*, where you can download models into Ollama (for example `qwen2.5:7b`) and delete them, with a progress bar.
- **Building an installer:** `npm run dist` makes a portable Windows .exe; use `dist:mac` or `dist:linux` on those systems.
- **Settings:** saved servers live in the app's user-data folder (`config.json`), on this computer only.

## 4. Phones

Both apps do three things: **Connect**, **Health** sync and **Exercise** rep counting.

1. Find the computer's network address (for example `192.168.1.20`). Phones can't use `localhost`.
2. In the app, open **Connect**, enter `http://192.168.1.20:8080`, then tap **Connect**. The app shows its **device ID** and says *Waiting for the operator*.
3. On the website, sign in as mission control or flight surgeon and open **Devices**. The phone is listed as pending. Check that the first characters of the ID match the phone, then choose the crew member.
4. The phone switches to *Connected as …* within about 5 seconds. **Health › Sync** uploads wearable data, and **Exercise** counts reps and saves workouts. Everything lands on that crew member's dashboard and in the Exercise page history.

**Android:** open `android/` in Android Studio and run it. From the command line, `gradlew assembleDebug` builds `app/build/outputs/apk/debug/app-debug.apk`. The emulator reaches your computer at `http://10.0.2.2:8080`.

**iPhone:** open `ios/HealthMonitor/HealthMonitor.xcodeproj` in Xcode on a Mac, set your signing team, then build and run on a device. HealthKit and the camera don't work in the simulator.

## 5. Local AI (assistant and models)

1. Install Ollama, then pull a model:

   ```bash
   ollama pull qwen2.5:7b
   ```

   You can also use the desktop app's model manager or the website's **Fine-tuning › Models** tab.
2. With `ASSISTANT_PROVIDER=auto`, the assistant uses Ollama when no OpenAI key is set.

## 6. Fine-tuning (optional, NVIDIA GPU)

On the GPU machine:

```bash
python -m venv .venv-train
```

```bash
.venv-train/Scripts/pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124
```

```bash
.venv-train/Scripts/pip install -r llm/requirements-train.txt
```

```bash
.venv-train/Scripts/python -m uvicorn llm.service.trainer_service:app --port 8600
```

Then set `HMT_LLM_TRAINER_URL=http://host.docker.internal:8600` in `.env` and restart the API. If you set a `HMT_TRAINER_TOKEN`, use the same value on both sides. Collect the sources, build the dataset, train, evaluate and deploy from **AI › Fine-tuning**. Details are in [llm/FINE_TUNING.md](llm/FINE_TUNING.md).

## 6b. Habitat sensors (MQTT)

The broker starts with the stack on port 1883. See [MQTT_HABITAT.md](MQTT_HABITAT.md).

## 7. Online demo

See [DEPLOY_DIGITALOCEAN.md](DEPLOY_DIGITALOCEAN.md).

## Where things are stored (all local)

| Data | Location |
|---|---|
| Database | Docker volume `pgdata` (serious edition: `pgdata_serious`) |
| LLM corpus, datasets, runs, evaluations, search index | `data/llm/` (git-ignored) |
| Research datasets for the AI models | `data/external/` (git-ignored) |
| Desktop app settings | Electron user-data folder |
| Phone pairing | Phone keychain / app preferences; server table `devices` |
| Server connections | Server table `server_connections` |
