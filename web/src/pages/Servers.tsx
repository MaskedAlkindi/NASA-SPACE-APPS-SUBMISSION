import { useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Badge, Card, Loading } from "../components/ui";
import { useApi } from "../hooks";

type Connector = { id: string; name: string; description: string; default_url: string; url_hint: string };
type Conn = { id: number; name: string; kind: string; url: string; enabled: boolean; settings: Record<string, string>;
  last_checked: string | null; last_status: string; last_message: string; last_data: Record<string, any> };

export default function Servers() {
  const { user } = useAuth();
  const operator = user?.role !== "astronaut";
  const connectors = useApi<{ connectors: Connector[] }>("/servers/connectors");
  const conns = useApi<{ connections: Conn[] }>("/servers");
  const [kind, setKind] = useState("noaa_swpc");
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState<string | number>("");
  const [err, setErr] = useState("");
  const chosen = connectors.data?.connectors.find((c) => c.id === kind);

  async function run(key: string | number, fn: () => Promise<unknown>) {
    setBusy(key); setErr("");
    try { await fn(); conns.reload(); } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } finally { setBusy(""); }
  }
  function add() {
    run("add", async () => {
      await api("/servers", { body: { name: name || chosen?.name || kind, kind, url: url || chosen?.default_url, settings: token ? { token } : {} } });
      setName(""); setUrl(""); setToken("");
    });
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Servers</h1>
          <p>Links from this HEALTH-01 installation to other servers and online information: live space weather, another HEALTH-01 server, an LLM server, or any JSON URL. Settings are stored on this server.</p>
        </div>
      </div>
      {err && <div className="err">{err}</div>}
      {operator && (
        <Card title="Add a connection">
          <div className="grid g4">
            <label className="field">Kind
              <select className="input" value={kind} onChange={(e) => { setKind(e.target.value); setUrl(""); }}>
                {(connectors.data?.connectors ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <label className="field">Name<input className="input" value={name} placeholder={chosen?.name} onChange={(e) => setName(e.target.value)} /></label>
            <label className="field">URL<input className="input mono" value={url} placeholder={chosen?.default_url || chosen?.url_hint} onChange={(e) => setUrl(e.target.value)} /></label>
            {kind === "json_feed"
              ? <label className="field">Bearer token (optional)<input className="input" type="password" value={token} onChange={(e) => setToken(e.target.value)} /></label>
              : <div />}
          </div>
          <p className="small muted">{chosen?.description}</p>
          <button className="btn primary" disabled={busy === "add" || (!url && !chosen?.default_url)} onClick={add}>{busy === "add" ? "Connecting…" : "Add and test"}</button>
        </Card>
      )}
      {conns.loading && !conns.data && <Loading what="Connections" />}
      {conns.data && conns.data.connections.length === 0 && <div className="empty">No connections yet. {operator ? "Try NOAA space weather: it needs no setup." : "An operator can add them."}</div>}
      <div className="grid g2">
        {(conns.data?.connections ?? []).map((c) => (
          <Card key={c.id} title={c.name} extra={<span className="row">
            <Badge kind={c.last_status === "ok" ? "ok" : c.last_status === "error" ? "warning" : "neutral"}>{c.last_status}</Badge>
            <button className="btn ghost" disabled={busy === c.id} onClick={() => run(c.id, () => api(`/servers/${c.id}/check`, { method: "POST" }))}>{busy === c.id ? "…" : "Check now"}</button>
            {operator && <button className="btn ghost danger" onClick={() => confirm(`Remove ${c.name}?`) && run(c.id, () => api(`/servers/${c.id}`, { method: "DELETE" }))}>Remove</button>}
          </span>}>
            <div className="small mono faint">{c.kind} · {c.url}</div>
            <p>{c.last_message}</p>
            <DataView kind={c.kind} data={c.last_data} />
            <div className="small faint">checked {c.last_checked ? new Date(c.last_checked).toLocaleString() : "never"}</div>
          </Card>
        ))}
      </div>
    </>
  );
}

function DataView({ kind, data }: { kind: string; data: Record<string, any> }) {
  if (!data || !Object.keys(data).length) return null;
  if (kind === "noaa_swpc") {
    return (
      <div className="grid g2" style={{ marginBottom: 8 }}>
        <div className="tile"><div className="label">Geomagnetic (Kp)</div><div className="value">{data.kp?.toFixed?.(2)}</div><div className="sub">NOAA scale {data.geomagnetic_scale} · {data.kp_time}</div></div>
        <div className="tile"><div className="label">Protons ≥10 MeV</div><div className="value">{data.proton_flux_10mev_pfu ?? "—"}<span className="unit">pfu</span></div><div className="sub">NOAA scale {data.radiation_storm_scale} · {data.proton_time}</div></div>
      </div>
    );
  }
  if (kind === "ollama" && Array.isArray(data.models)) {
    return (
      <table className="tbl"><thead><tr><th>Model</th><th>Size</th><th>Params</th><th>Quant</th></tr></thead>
        <tbody>{data.models.map((m: any) => <tr key={m.name}><td className="mono">{m.name}</td><td>{m.size_gb} GB</td><td>{m.parameters}</td><td>{m.quantization}</td></tr>)}</tbody></table>
    );
  }
  return <pre className="small mono" style={{ whiteSpace: "pre-wrap", margin: "6px 0" }}>{JSON.stringify(data, null, 2).slice(0, 1200)}</pre>;
}
