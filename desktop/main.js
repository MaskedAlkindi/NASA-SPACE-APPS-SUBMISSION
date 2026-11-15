// HEALTH-01 desktop app (Electron).
// The app shows the normal HEALTH-01 website from a server you choose (local Docker, a LAN server, or the online demo),
// so the website keeps working in any browser. Desktop extras: saved servers, starting the local Docker stack,
// and managing local AI models in Ollama (download / delete) without the command line.
const { app, BrowserWindow, Menu, ipcMain, shell, dialog } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const CONFIG = () => path.join(app.getPath("userData"), "config.json");
const DEFAULTS = {
  servers: [
    { name: "This computer (Docker)", url: "http://localhost:8080" },
    { name: "Development (Vite)", url: "http://localhost:5173" },
  ],
  current: null,
  ollamaUrl: "http://localhost:11434",
  repoDir: path.resolve(__dirname, ".."),
};

function loadConfig() {
  try { return { ...DEFAULTS, ...JSON.parse(fs.readFileSync(CONFIG(), "utf8")) }; } catch { return { ...DEFAULTS }; }
}
function saveConfig(c) {
  fs.mkdirSync(path.dirname(CONFIG()), { recursive: true });
  fs.writeFileSync(CONFIG(), JSON.stringify(c, null, 2));
}

let win = null;
let modelsWin = null;

function validUrl(u) {
  try { const x = new URL(u); return x.protocol === "http:" || x.protocol === "https:"; } catch { return false; }
}

function openConnect() {
  win.loadFile(path.join(__dirname, "renderer", "connect.html"));
}

function openServer(url) {
  const target = url.replace(/\/+$/, "") + "/app";
  win.loadURL(target).catch(() => openConnect());
}

function createWindow() {
  win = new BrowserWindow({
    width: 1400, height: 900, minWidth: 900, minHeight: 600, title: "HEALTH-01",
    icon: path.join(__dirname, "assets", "icon.png"), backgroundColor: "#0b1220",
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  // Links to other sites open in the system browser, not inside the app.
  win.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: "deny" }; });
  win.webContents.on("did-fail-load", (_e, code, desc, url) => {
    if (code !== -3 && !url.startsWith("file:")) {
      dialog.showMessageBox(win, { type: "warning", message: `Could not reach ${url}`, detail: `${desc}. Pick another server or start the local stack.` });
      openConnect();
    }
  });
  if (process.env.HEALTH01_SMOKE) {     // CI / smoke test: load, report, quit
    win.webContents.on("did-finish-load", async () => {
      const title = await win.webContents.executeJavaScript("document.title + ' | ' + (document.body.innerText || '').slice(0, 120).replace(/\\s+/g, ' ')");
      console.log(`SMOKE loaded ${win.webContents.getURL()} :: ${title}`);
      setTimeout(() => app.quit(), 500);
    });
  }
  const cfg = loadConfig();
  if (process.env.HEALTH01_SMOKE_URL) openServer(process.env.HEALTH01_SMOKE_URL);
  else if (cfg.current && validUrl(cfg.current)) openServer(cfg.current); else openConnect();
  buildMenu();
}

function openModels() {
  if (modelsWin && !modelsWin.isDestroyed()) { modelsWin.focus(); return; }
  modelsWin = new BrowserWindow({
    width: 900, height: 700, title: "HEALTH-01 · Local AI models", parent: win, backgroundColor: "#0b1220",
    webPreferences: { preload: path.join(__dirname, "preload.js"), contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  modelsWin.loadFile(path.join(__dirname, "renderer", "models.html"));
}

function buildMenu() {
  const cfg = loadConfig();
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    { label: "HEALTH-01", submenu: [
      { label: "Switch server…", accelerator: "CmdOrCtrl+K", click: openConnect },
      { label: "Landing page", click: () => cfg.current && win.loadURL(cfg.current) },
      { label: "Open in browser", click: () => cfg.current && shell.openExternal(cfg.current + "/app") },
      { type: "separator" }, { role: "quit" } ] },
    { label: "AI", submenu: [
      { label: "Local AI models…", accelerator: "CmdOrCtrl+M", click: openModels },
      { label: "Fine-tuning workspace", click: () => cfg.current && win.loadURL(cfg.current + "/app/fine-tuning") } ] },
    { label: "View", submenu: [{ role: "reload" }, { role: "toggleDevTools" }, { type: "separator" }, { role: "resetZoom" }, { role: "zoomIn" }, { role: "zoomOut" }, { role: "togglefullscreen" }] },
  ]));
}

// ---------------------------------------------------------------- IPC (renderer pages call these through preload.js)
ipcMain.handle("config:get", () => loadConfig());
ipcMain.handle("server:open", (_e, url) => {
  if (!validUrl(url)) throw new Error("Server address must start with http:// or https://");
  const c = loadConfig();
  c.current = url.replace(/\/+$/, "");
  if (!c.servers.some((s) => s.url === c.current)) c.servers.push({ name: new URL(c.current).host, url: c.current });
  saveConfig(c); buildMenu(); openServer(c.current);
  return true;
});
ipcMain.handle("server:remove", (_e, url) => { const c = loadConfig(); c.servers = c.servers.filter((s) => s.url !== url); saveConfig(c); return c; });
ipcMain.handle("server:check", async (_e, url) => {
  if (!validUrl(url)) return { ok: false, error: "invalid address" };
  try {
    const r = await fetch(url.replace(/\/+$/, "") + "/api/v1/health", { signal: AbortSignal.timeout(4000) });
    return { ok: r.ok, ...(await r.json()) };
  } catch (e) { return { ok: false, error: String(e.message || e) }; }
});
ipcMain.handle("stack:start", async () => {
  const c = loadConfig();
  if (!fs.existsSync(path.join(c.repoDir, "docker-compose.yml"))) throw new Error(`docker-compose.yml not found in ${c.repoDir}`);
  return new Promise((resolve) => {
    const p = spawn("docker", ["compose", "up", "-d"], { cwd: c.repoDir, shell: false });
    let out = "";
    p.stdout.on("data", (d) => (out += d)); p.stderr.on("data", (d) => (out += d));
    p.on("error", (e) => resolve({ ok: false, log: String(e) }));
    p.on("close", (code) => resolve({ ok: code === 0, log: out.slice(-3000) }));
  });
});
ipcMain.handle("ollama:setUrl", (_e, url) => { if (!validUrl(url)) throw new Error("invalid URL"); const c = loadConfig(); c.ollamaUrl = url; saveConfig(c); return true; });
ipcMain.handle("ollama:list", async () => {
  const c = loadConfig();
  try {
    const r = await fetch(c.ollamaUrl + "/api/tags", { signal: AbortSignal.timeout(5000) });
    return { ok: true, url: c.ollamaUrl, ...(await r.json()) };
  } catch (e) { return { ok: false, url: c.ollamaUrl, error: String(e.message || e), models: [] }; }
});
ipcMain.handle("ollama:delete", async (_e, name) => {
  const c = loadConfig();
  const r = await fetch(c.ollamaUrl + "/api/delete", { method: "DELETE", body: JSON.stringify({ name }), headers: { "Content-Type": "application/json" } });
  if (!r.ok) throw new Error(await r.text());
  return true;
});
ipcMain.on("ollama:pull", async (e, name) => {
  // Streams progress events back to the window that asked.
  const c = loadConfig();
  const send = (msg) => { if (!e.sender.isDestroyed()) e.sender.send("ollama:pull-progress", { name, ...msg }); };
  try {
    const r = await fetch(c.ollamaUrl + "/api/pull", { method: "POST", body: JSON.stringify({ name, stream: true }), headers: { "Content-Type": "application/json" } });
    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
        if (!line) continue;
        const ev = JSON.parse(line);
        if (ev.error) { send({ error: ev.error, done: true }); return; }
        send({ status: ev.status, completed: ev.completed, total: ev.total });
      }
    }
    send({ status: "success", done: true });
  } catch (err) { send({ error: String(err.message || err), done: true }); }
});

app.whenReady().then(createWindow);
app.on("window-all-closed", () => { if (process.platform !== "darwin") app.quit(); });
app.on("activate", () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
