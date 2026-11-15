# HEALTH-01 desktop app (Electron)

The desktop app opens the normal HEALTH-01 website from a server you choose. The website itself is unchanged and keeps working in any browser.

| | |
|---|---|
| **Servers** | Saved list with online/offline status, plus "add any URL": this computer, a crew server, or the online demo. Ctrl+K switches. |
| **Local stack** | "Start local stack" runs `docker compose up -d` in the repository folder |
| **Local AI models** | Ctrl+M opens the Ollama model manager: list, download with progress, delete |
| **Settings** | Stored in the app's user-data folder (`config.json`), on this computer only |

## Run

```bash
npm install
```

```bash
npm start
```

## Smoke test (no clicks)

`HEALTH01_SMOKE=1 npm start` loads the start page, prints its title and quits. Add `HEALTH01_SMOKE_URL=http://localhost:8080` to load the demo instead.

## Package

```bash
npm run dist
```

This builds a portable Windows `.exe` in `dist/`. Use `dist:mac` or `dist:linux` on those systems.

## Security

Remote pages run with context isolation, a sandbox and no Node.js access. Links to other sites open in the system browser. The local pages have a strict Content-Security-Policy.
