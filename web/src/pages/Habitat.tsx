import { useEffect, useState } from "react";
import { api } from "../api";
import { useAuth } from "../auth";
import { Badge, Card, Loading } from "../components/ui";
import { useApi } from "../hooks";

type Mapping = { id: number; topic: string; metric: string; json_path: string; scale: number; offset: number; astronaut_id: string | null;
  data_class: string; min_interval_s: number; label: string; enabled: boolean; last_value: number | null; last_at: string | null; last_error: string };
type Over = {
  broker: { host: string; port: number; username: string; password: string; tls: boolean; discover: string; enabled: boolean };
  status: { connected: boolean; error: string; host: string | null; messages: number };
  mappings: Mapping[]; seen: { topic: string; payload: string; at: string; count: number }[];
  metrics: { metric: string; label: string; unit: string; environment: boolean }[];
  presets: { label: string; scale: number; offset: number }[];
};
const EMPTY = { topic: "", metric: "cabin_co2", json_path: "", scale: 1, offset: 0, astronaut_id: "", data_class: "real", min_interval_s: 10, label: "" };

export default function Habitat() {
  const { user } = useAuth();
  const op = user?.role !== "astronaut";
  const o = useApi<Over>("/mqtt");
  const crew = useApi<{ astronauts: { id: string; callsign: string }[] }>("/astronauts");
  const [broker, setBroker] = useState<Over["broker"] | null>(null);
  const [form, setForm] = useState<typeof EMPTY | null>(null);
  const [sample, setSample] = useState("");
  const [preview, setPreview] = useState<string>("");
  const [err, setErr] = useState("");
  useEffect(() => { if (o.data && !broker) setBroker(o.data.broker); }, [o.data, broker]);
  useEffect(() => { const t = setInterval(o.reload, 4000); return () => clearInterval(t); }, [o.reload]);
  useEffect(() => {
    if (!form || !sample) { setPreview(""); return; }
    api("/mqtt/preview", { body: { payload: sample, json_path: form.json_path, scale: form.scale, offset: form.offset } })
      .then((r) => setPreview(r.ok ? `→ ${r.value} ${o.data?.metrics.find((m) => m.metric === form.metric)?.unit ?? ""}` : r.error)).catch(() => {});
  }, [form, sample]);   // eslint-disable-line react-hooks/exhaustive-deps

  async function run(fn: () => Promise<unknown>) { setErr(""); try { await fn(); o.reload(); } catch (e) { setErr(e instanceof Error ? e.message : "Failed"); } }
  const d = o.data;
  if (!d) return <Loading what="Habitat sensors" />;
  const metric = d.metrics.find((m) => m.metric === form?.metric);
  const mapped = new Set(d.mappings.map((m) => m.topic));

  return (
    <>
      <div className="page-head"><div><h1>Habitat sensors</h1><p>Sensors publish over MQTT. Pick a topic, choose what it measures, done.</p></div></div>
      {err && <div className="err">{err}</div>}

      <div className="grid g2">
        <Card title="Broker" extra={<Badge kind={d.status.connected ? "ok" : d.broker.enabled ? "caution" : "neutral"}>{d.status.connected ? "connected" : d.broker.enabled ? d.status.error || "connecting" : "off"}</Badge>}>
          {broker && (
            <>
              <div className="grid g2">
                <label className="field">Host<input className="input mono" value={broker.host} disabled={!op} onChange={(e) => setBroker({ ...broker, host: e.target.value })} /></label>
                <label className="field">Port<input className="input mono" type="number" value={broker.port} disabled={!op} onChange={(e) => setBroker({ ...broker, port: Number(e.target.value) })} /></label>
                <label className="field">Username<input className="input" value={broker.username} disabled={!op} onChange={(e) => setBroker({ ...broker, username: e.target.value })} /></label>
                <label className="field">Password<input className="input" type="password" value={broker.password} disabled={!op} onChange={(e) => setBroker({ ...broker, password: e.target.value })} /></label>
                <label className="field">Listen for topics<input className="input mono" value={broker.discover} disabled={!op} onChange={(e) => setBroker({ ...broker, discover: e.target.value })} /></label>
                <label className="field">TLS<select className="input" value={broker.tls ? "1" : "0"} disabled={!op} onChange={(e) => setBroker({ ...broker, tls: e.target.value === "1" })}><option value="0">off</option><option value="1">on</option></select></label>
              </div>
              {op && <div className="row" style={{ marginTop: 10 }}>
                <button className="btn primary" onClick={() => run(() => api("/mqtt/broker", { method: "PUT", body: { ...broker, enabled: true } }))}>Connect</button>
                <button className="btn ghost" onClick={() => run(() => api("/mqtt/broker", { method: "PUT", body: { ...broker, enabled: false } }))}>Disconnect</button>
                <span className="small faint">{d.status.messages} messages</span>
              </div>}
            </>
          )}
        </Card>

        <Card title="Topics seen" extra={<span className="small faint">newest first</span>}>
          {d.seen.length === 0 && <div className="empty">Nothing yet. Connect, then power on a sensor.</div>}
          <div className="col" style={{ maxHeight: 300, overflowY: "auto" }}>
            {d.seen.map((s) => (
              <div key={s.topic} className="row" style={{ justifyContent: "space-between", borderBottom: "1px dashed var(--border-soft)", paddingBottom: 6 }}>
                <div style={{ minWidth: 0 }}><b className="mono small">{s.topic}</b><div className="small faint mono" style={{ overflowWrap: "anywhere" }}>{s.payload.slice(0, 90)}</div></div>
                {op && (mapped.has(s.topic) ? <Badge kind="ok">assigned</Badge>
                  : <button className="btn" onClick={() => { setForm({ ...EMPTY, topic: s.topic }); setSample(s.payload); }}>Assign</button>)}
              </div>
            ))}
          </div>
        </Card>
      </div>

      {form && op && (
        <Card title={`Assign ${form.topic || "topic"}`}>
          <div className="grid g4">
            <label className="field">Topic<input className="input mono" value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })} /></label>
            <label className="field">Measures
              <select className="input" value={form.metric} onChange={(e) => setForm({ ...form, metric: e.target.value })}>
                <optgroup label="Habitat">{d.metrics.filter((m) => m.environment).map((m) => <option key={m.metric} value={m.metric}>{m.label} ({m.unit})</option>)}</optgroup>
                <optgroup label="Person">{d.metrics.filter((m) => !m.environment).map((m) => <option key={m.metric} value={m.metric}>{m.label} ({m.unit})</option>)}</optgroup>
              </select>
            </label>
            {metric && !metric.environment && (
              <label className="field">Crew member
                <select className="input" value={form.astronaut_id} onChange={(e) => setForm({ ...form, astronaut_id: e.target.value })}>
                  <option value="">choose…</option>{(crew.data?.astronauts ?? []).map((a) => <option key={a.id} value={a.id}>{a.callsign}</option>)}
                </select>
              </label>
            )}
            <label className="field">JSON field (blank = number)<input className="input mono" value={form.json_path} placeholder="e.g. t or data.co2" onChange={(e) => setForm({ ...form, json_path: e.target.value })} /></label>
            <label className="field">Convert
              <select className="input" onChange={(e) => { const p = d.presets[Number(e.target.value)]; setForm({ ...form, scale: p.scale, offset: p.offset }); }}>
                {d.presets.map((p, i) => <option key={p.label} value={i}>{p.label}</option>)}
              </select>
            </label>
            <label className="field">Data<select className="input" value={form.data_class} onChange={(e) => setForm({ ...form, data_class: e.target.value })}><option value="real">real sensor</option><option value="simulated">simulated</option></select></label>
            <label className="field">Store every (s)<input className="input" type="number" value={form.min_interval_s} onChange={(e) => setForm({ ...form, min_interval_s: Number(e.target.value) })} /></label>
            <label className="field">Name<input className="input" value={form.label} placeholder="Module A CO₂" onChange={(e) => setForm({ ...form, label: e.target.value })} /></label>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <input className="input mono" style={{ flex: 1 }} value={sample} placeholder="sample payload" onChange={(e) => setSample(e.target.value)} />
            <span className="mono">{preview}</span>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <button className="btn primary" onClick={() => run(async () => { await api("/mqtt/mappings", { body: { ...form, astronaut_id: form.astronaut_id || null } }); setForm(null); })}>Save</button>
            <button className="btn ghost" onClick={() => setForm(null)}>Cancel</button>
          </div>
        </Card>
      )}

      <Card title="Assigned sensors" extra={op && !form && <button className="btn" onClick={() => { setForm({ ...EMPTY }); setSample(""); }}>Add manually</button>}>
        {d.mappings.length === 0 && <div className="empty">No sensors assigned.</div>}
        {d.mappings.length > 0 && (
          <div className="table-wrap"><table className="tbl">
            <thead><tr><th>Sensor</th><th>Measures</th><th>Latest</th><th>Data</th><th></th></tr></thead>
            <tbody>{d.mappings.map((m) => {
              const md = d.metrics.find((x) => x.metric === m.metric);
              return (
                <tr key={m.id}>
                  <td><b>{m.label || m.topic}</b><div className="small faint mono">{m.topic}{m.json_path && ` › ${m.json_path}`}</div></td>
                  <td>{md?.label}{m.astronaut_id && <div className="small faint">{m.astronaut_id}</div>}</td>
                  <td className="mono">{m.last_value ?? "—"} {md?.unit}{m.last_error && <div className="small err">{m.last_error}</div>}</td>
                  <td><Badge kind={m.data_class === "simulated" ? "sim" : "real"}>{m.data_class}</Badge></td>
                  <td>{op && <button className="btn ghost danger" onClick={() => confirm("Remove this sensor?") && run(() => api(`/mqtt/mappings/${m.id}`, { method: "DELETE" }))}>Remove</button>}</td>
                </tr>
              );
            })}</tbody>
          </table></div>
        )}
      </Card>
    </>
  );
}
