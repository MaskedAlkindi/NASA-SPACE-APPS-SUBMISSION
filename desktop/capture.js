// Screenshot tool for docs: npx electron capture.js [baseUrl] [outDir]
// Logs in as the flight surgeon (sees every page), skips the first-visit tour, captures desktop + iPad sizes.
const { app, BrowserWindow } = require("electron");
const fs = require("node:fs");
const path = require("node:path");

const BASE = process.argv[2] || "http://localhost:8080";
const OUT = path.resolve(process.argv[3] || path.join(__dirname, "..", "docs", "screenshots"));
const USER = process.env.CAPTURE_USER || "flight-surgeon";
const PASS = process.env.CAPTURE_PASS || "hmt-demo";
const SHOTS = [
  ["01-landing", "/", 1440, 900, false],
  ["02-overview", "/app/", 1440, 900, true],
  ["03-dashboard", "/app/dashboard?a=AST-004", 1440, 900, true],
  ["04-exercise", "/app/exercise?a=AST-002", 1440, 900, true],
  ["05-insights", "/app/intelligence?a=AST-001", 1440, 900, true],
  ["06-ai-models", "/app/ai-models?a=AST-001", 1440, 900, true],
  ["07-simulator", "/app/simulator", 1440, 900, true],
  ["08-habitat-sensors", "/app/habitat", 1440, 900, true],
  ["09-devices", "/app/devices", 1440, 900, true],
  ["10-servers", "/app/servers", 1440, 900, true],
  ["11-fine-tuning", "/app/fine-tuning", 1440, 900, true],
  ["12-settings-hazards", "/app/settings?tab=hazards", 1440, 900, true],
  ["13-settings-about", "/app/settings?tab=about", 1440, 900, true],
  ["14-ipad-overview", "/app/", 1024, 1366, true],
  ["15-ipad-exercise", "/app/exercise?a=AST-002", 1024, 1366, true],
  ["16-walkthrough", "/app/?tour=1", 1440, 900, "tour"],
];
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

app.whenReady().then(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const win = new BrowserWindow({ show: false, width: 1440, height: 900, webPreferences: { offscreen: true } });
  await win.loadURL(BASE + "/app/");
  await win.webContents.executeJavaScript(`fetch('/api/v1/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:${JSON.stringify(USER)},passcode:${JSON.stringify(PASS)}})}).then(r=>r.json()).then(j=>{
    localStorage.setItem('hmt.token',j.access_token);localStorage.setItem('hmt.user',JSON.stringify(j.user));})`);
  for (const [name, url, w, h, auth] of SHOTS) {
    win.setContentSize(w, h);
    await win.webContents.executeJavaScript(auth === "tour" ? "document.cookie='h01_onboarded=; max-age=0; path=/'" : "document.cookie='h01_onboarded=1; max-age=31536000; path=/'");
    await win.loadURL(BASE + url);
    await wait(name.includes("simulator") || name.includes("models") ? 4500 : 3000);
    const img = await win.webContents.capturePage();
    fs.writeFileSync(path.join(OUT, name + ".png"), img.toPNG());
    console.log("saved", name);
  }
  app.quit();
});
