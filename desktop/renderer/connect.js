const $ = (id) => document.getElementById(id);

async function render() {
  const cfg = await window.health01.config();
  const box = $("servers");
  box.textContent = "";
  for (const s of cfg.servers) {
    const row = document.createElement("div");
    row.className = "server";
    const dot = document.createElement("span"); dot.className = "dot";
    const info = document.createElement("div"); info.className = "grow";
    const b = document.createElement("b"); b.textContent = s.name;
    const small = document.createElement("small"); small.textContent = s.url + " · checking…";
    info.append(b, small);
    const open = document.createElement("button"); open.className = "primary"; open.textContent = "Open";
    open.onclick = () => window.health01.openServer(s.url).catch((e) => alert(e.message));
    const rm = document.createElement("button"); rm.className = "danger"; rm.textContent = "Remove";
    rm.onclick = async () => { await window.health01.removeServer(s.url); render(); };
    row.append(dot, info, open, rm);
    box.append(row);
    window.health01.checkServer(s.url).then((h) => {
      dot.className = "dot " + (h.ok ? "ok" : "bad");
      small.textContent = s.url + (h.ok ? ` · online · assistant ${h.assistant_mode || "?"}` : ` · offline (${h.error || "no answer"})`);
    });
  }
}

$("add").onclick = () => window.health01.openServer($("url").value.trim()).catch((e) => alert(e.message));
$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") $("add").click(); });
$("models").onclick = () => location.href = "models.html";
$("start").onclick = async () => {
  const btn = $("start"), log = $("log");
  btn.disabled = true; btn.textContent = "Starting… (first start builds images, a few minutes)";
  log.hidden = false; log.textContent = "docker compose up -d";
  try {
    const r = await window.health01.startStack();
    log.textContent = r.log || (r.ok ? "Started." : "Failed.");
    if (r.ok) setTimeout(render, 4000);
  } catch (e) { log.textContent = e.message; }
  btn.disabled = false; btn.textContent = "Start local stack (Docker)";
};
render();
