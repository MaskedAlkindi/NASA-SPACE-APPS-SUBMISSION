# Push, redeploy, test everything

## 1. Push (from your PC)

```powershell
git add -A
git commit -m "Crew admin, sketch landing, GPU trainer, MQTT live simulator"
git push origin main
```

## 2. Redeploy the website server

```bash
ssh root@YOUR_SERVER
cd ~/health01        # wherever the repo lives
./deploy/digitalocean/update.sh
```

Keeps the database. On start-up the crew is renamed and Mohmmed (AST-005) gets his simulated history.
Old logins (`orion`, `vega`, `lyra`, `atlas`) are removed.

Local serious edition instead: `cd deploy\serious; docker compose up -d --build`

## 3. GPU server (bigger models + fine-tuning)

See [llm/GPU_SERVER.md](llm/GPU_SERVER.md). The setup script sends the last **commit**, so commit before this. Short version:

```powershell
.\scripts\gpu_server.ps1 -Server user@GPU_IP -Action setup     # once
.\scripts\gpu_server.ps1 -Server user@GPU_IP -Action tunnel    # keep open
cd deploy\serious; docker compose up -d api
```

Read the real hardware before choosing a model (the repo does not contain a live server IP):

```bash
nvidia-smi
free -h
nproc
```

## 4. MQTT live simulator

Not started by `docker compose up`. After the API is up:

```powershell
.\scripts\mqtt_sim.ps1
```

On the website server, from the repo directory (the server passcode is the one in `.env`, not always `hmt-demo`):

```bash
set -a; source .env; set +a
./scripts/mqtt_sim.sh
```

Habitat sensors then shows simulated cabin readings. Stop with `.\scripts\mqtt_sim.ps1 down`.

## 5. Test checklist

Passcode for every account: `hmt-demo`. Site password: `staydetermined`.

**Landing (no password)**
- [ ] `/` opens straight away, no password page
- [ ] Looks hand-drawn: circled "healthy", taped photo, arrows
- [ ] "meet the crew": 5 cartoon polaroids
- [ ] About: HajidAlkindi.com, LinkedIn, Instagram @starlitoman (credit to Mohmmed Alwahabi) open
- [ ] Phone width: nothing cut off

**Demo gate + login**
- [ ] "Open the demo" asks for the site password once, then shows the login
- [ ] Login shows only logo, name, usernames, passcode. No extra text
- [ ] Search box filters usernames (try `ha`)

**Mission Control = admin** (`mission-control`)
- [ ] Menu has **Admin → Crew**
- [ ] Crew page: 5 astronauts + pilot, each with a portrait
- [ ] Edit a role, save, it sticks; change it back
- [ ] Add a passcode (label "Judges", 6+ characters)
- [ ] Sign out, sign in as `mission-control` with the new passcode: works
- [ ] Remove it: that passcode no longer works

**Other roles**
- [ ] `flight-surgeon`: no Crew menu; `/app/crew` sends you home
- [ ] `hajid`: sees only his own data; avatar shows in the astronaut tabs

**Earlier features (quick pass)**
- [ ] Simulator runs, clock shows SIM time, "Discard simulation" restores
- [ ] Exercise: camera counts reps, guided workout plays
- [ ] Habitat sensors page shows MQTT readings
- [ ] Fine-tuning page: trainer shows "reachable" when the GPU tunnel is open
- [ ] Models: `qwen2.5:32b` / `72b` listed from the GPU server

## What was checked before handing over
- Backend tests: 72 passed. AI tests: 25 passed. Web type-check and build: clean.
- Local serious edition rebuilt; landing, gate, login search, Crew page checked in a browser.
- Not checked: the GPU server and the remote website server (no access from here).
