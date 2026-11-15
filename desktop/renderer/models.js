const $ = (id) => document.getElementById(id);
const api = window.health01.ollama;

async function refresh() {
  const r = await api.list();
  $("ollama").value = r.url;
  $("status").textContent = r.ok ? `Connected · ${r.models.length} model(s)` : `Not reachable: ${r.error}. Install Ollama from ollama.com and start it.`;
  const tb = $("list");
  tb.textContent = "";
  for (const m of r.models || []) {
    const tr = document.createElement("tr");
    const cells = [m.name, `${(m.size / 1e9).toFixed(2)} GB`, m.details?.parameter_size || "", m.details?.quantization_level || ""];
    for (const c of cells) { const td = document.createElement("td"); td.textContent = c; tr.append(td); }
    const td = document.createElement("td");
    const del = document.createElement("button"); del.className = "danger"; del.textContent = "Delete";
    del.onclick = async () => { if (confirm(`Delete ${m.name}?`)) { await api.remove(m.name).catch((e) => alert(e.message)); refresh(); } };
    td.append(del); tr.append(td); tb.append(tr);
  }
}

api.onProgress((p) => {
  $("progress").hidden = false;
  if (p.error) { $("ptext").textContent = `${p.name}: ${p.error}`; $("pull").disabled = false; return; }
  const pct = p.total ? Math.round((100 * (p.completed || 0)) / p.total) : null;
  $("ptext").textContent = `${p.name}: ${p.status}${pct !== null ? ` ${pct}%` : ""}`;
  if (pct !== null) $("pbar").style.width = pct + "%";
  if (p.done) { $("pull").disabled = false; refresh(); }
});

$("pull").onclick = () => { const n = $("name").value.trim(); if (!n) return; $("pull").disabled = true; api.pull(n); };
$("saveUrl").onclick = async () => { await api.setUrl($("ollama").value.trim()).catch((e) => alert(e.message)); refresh(); };
$("back").onclick = () => history.length > 1 ? history.back() : (location.href = "connect.html");
refresh();
