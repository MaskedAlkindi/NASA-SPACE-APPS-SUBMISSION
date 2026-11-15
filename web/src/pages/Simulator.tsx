import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, METRIC_LABEL, type Alert } from "../api";
import { isCrewWide, useAuth } from "../auth";
import { AlertItem, Badge, Card, chartTooltip, fmt } from "../components/ui";
import { useApi, useLive, type LiveMeasurement } from "../hooks";

const MAX_POINTS = 120;

export default function Simulator() {
  const { user } = useAuth();
  const sc = useApi<any>("/simulation/scenarios");
  const status = useApi<any>("/simulation/status");
  const [form, setForm] = useState({ scenario: "cardio_anomaly", astronaut_id: "AST-001", days: 4, severity: 1.0, tick_seconds: 1.0 });
  const [hr, setHr] = useState<Record<string, any>[]>([]);
  const [env, setEnv] = useState<Record<string, any>[]>([]);
  const [feed, setFeed] = useState<LiveMeasurement[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [state, setState] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { if (status.data) setState(status.data); }, [status.data]);
  useEffect(() => { const t = setInterval(status.reload, 2000); return () => clearInterval(t); }, [status.reload]);

  useLive((e) => {
    if (e.type === "measurements") {
      const sim = e.items.filter((i) => i.data_class === "simulated");
      if (!sim.length) return;
      const ts = sim[0].timestamp.slice(5, 16).replace("T", " ");
      const hrRow: Record<string, any> = { t: ts };
      sim.filter((i) => i.metric === "heart_rate").forEach((i) => (hrRow[i.astronaut_id!] = i.value));
      if (Object.keys(hrRow).length > 1) setHr((h) => [...h, hrRow].slice(-MAX_POINTS));
      const envRow: Record<string, any> = { t: ts };
      sim.filter((i) => i.astronaut_id === null).forEach((i) => (envRow[i.metric] = i.value));
      if (Object.keys(envRow).length > 1) setEnv((h) => [...h, envRow].slice(-MAX_POINTS));
      setFeed((f) => [...sim.filter((i) => i.metric !== "heart_rate" || i.astronaut_id === form.astronaut_id), ...f].slice(0, 40));
    }
    if (e.type === "alert") setAlerts((a) => [e.alert, ...a].slice(0, 12));
    if (e.type === "simulation") setState(e.state);
  });

  const start = async () => {
    setErr(null); setHr([]); setEnv([]); setFeed([]); setAlerts([]);
    try { setState(await api("/simulation/start", { body: form })); } catch (e: any) { setErr(e.message); }
  };
  const stop = async () => { try { setState(await api("/simulation/stop", { method: "POST" })); } catch (e: any) { setErr(e.message); } };
  const reset = async () => {
    if (!confirm("Delete all simulated measurements and alerts and re-seed the demo history?")) return;
    try { await api("/simulation/reset", { method: "POST" }); status.reload(); setErr("Demo data re-seeded."); } catch (e: any) { setErr(e.message); }
  };

  const can = isCrewWide(user);
  const crew = sc.data?.crew ?? [];
  const envScenario = ["co2_scrubber_fault", "radiation_event"].includes(form.scenario);
  return (
    <>
      <div className="page-head">
        <div><h1>Simulator</h1><p>Synthetic crew data, fed through every model in real time.</p></div>
        <div className="spacer" />
        {state?.running ? <Badge kind="sim">RUNNING · {state.scenario}</Badge> : <Badge kind="neutral">idle</Badge>}
      </div>
      <div className="banner">Everything produced here is <b>SIMULATED</b> and stored with data class “simulated”. One simulated hour = {form.tick_seconds}s real time.</div>
      <div className="grid g3">
        <Card title="Scenario">
          <div className="col">
            <label className="field">Scenario
              <select className="input" value={form.scenario} onChange={(e) => setForm({ ...form, scenario: e.target.value })}>
                {(sc.data?.scenarios ?? []).map((s: any) => <option key={s.id} value={s.id}>{s.id.replace(/_/g, " ")}</option>)}
              </select>
            </label>
            <div className="small muted">{sc.data?.scenarios.find((s: any) => s.id === form.scenario)?.description}</div>
            <label className="field">Target astronaut {envScenario && <span className="faint">(habitat-wide scenario)</span>}
              <select className="input" disabled={envScenario} value={form.astronaut_id} onChange={(e) => setForm({ ...form, astronaut_id: e.target.value })}>
                {crew.map((c: any) => <option key={c.id} value={c.id}>{c.callsign} ({c.id})</option>)}
              </select>
            </label>
            <div className="grid g3" style={{ gap: 8 }}>
              <label className="field">Days<input className="input" type="number" min={1} max={30} value={form.days} onChange={(e) => setForm({ ...form, days: +e.target.value })} /></label>
              <label className="field">Severity<input className="input" type="number" step={0.1} min={0.2} max={2} value={form.severity} onChange={(e) => setForm({ ...form, severity: +e.target.value })} /></label>
              <label className="field">s / sim-hour<input className="input" type="number" step={0.1} min={0.05} max={30} value={form.tick_seconds} onChange={(e) => setForm({ ...form, tick_seconds: +e.target.value })} /></label>
            </div>
            <div className="row">
              <button className="btn primary" disabled={!can} onClick={start}>{state?.running ? "Restart" : "Start replay"}</button>
              <button className="btn danger" disabled={!can || !state?.running} onClick={stop}>Stop</button>
              <button className="btn ghost" disabled={!can} onClick={reset}>Reset demo data</button>
            </div>
            {!can && <div className="small faint">Mission control / flight surgeon role required to run the simulator.</div>}
            {err && <div className="small muted">{err}</div>}
            {state?.ticks > 0 && (
              <div className="col" style={{ gap: 6 }}>
                <div className="progress"><div style={{ width: `${(state.progress ?? 0) * 100}%` }} /></div>
                <div className="small faint">sim time {state.sim_time?.slice(0, 16).replace("T", " ")} · {state.ticks} h · {state.records_emitted} readings{state.finished && " · finished"}</div>
              </div>
            )}
            <div className="small faint">Episode starts on simulated day 2 so day 1 shows the baseline. Daily metrics (sleep, resting HR, HRV) arrive at 07:00 station time; check-ins at 20:00.</div>
          </div>
        </Card>
        <Card title="Live heart rate (all crew)" className="span2" extra={<span className="small faint">{hr.length} hourly ticks</span>}>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={hr} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="t" minTickGap={40} />
              <YAxis domain={["auto", "auto"]} />
              <Tooltip {...chartTooltip} />
              {crew.map((c: any, i: number) => <Line key={c.id} dataKey={c.id} name={c.callsign} isAnimationActive={false} dot={false}
                stroke={["#005c96", "#1d2bdb", "#d81b1b", "#b86e00"][i % 4]} strokeWidth={c.id === form.astronaut_id && !envScenario ? 2.6 : 1.2} />)}
            </LineChart>
          </ResponsiveContainer>
          {hr.length === 0 && <div className="empty">Start a replay to stream data here</div>}
        </Card>
        <Card title="Cabin CO₂ & radiation" className="span2">
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={env} margin={{ top: 6, right: 0, left: -12, bottom: 0 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="t" minTickGap={40} />
              <YAxis yAxisId="c" domain={[0, "auto"]} />
              <YAxis yAxisId="r" orientation="right" />
              <Tooltip {...chartTooltip} />
              <ReferenceLine yAxisId="c" y={3} stroke="#b86e00" strokeDasharray="4 4" />
              <ReferenceLine yAxisId="c" y={4} stroke="#d81b1b" strokeDasharray="4 4" />
              <Line yAxisId="c" dataKey="cabin_co2" name="CO₂ (mmHg)" stroke="#b86e00" dot={false} isAnimationActive={false} />
              <Line yAxisId="r" dataKey="radiation_dose_rate" name="Dose rate (µGy/h)" stroke="#6b4fbb" dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
          <div className="small faint">Dashed lines: demo CO₂ caution (3 mmHg) and warning (4 mmHg) thresholds. These are demo values, not a flight standard.</div>
        </Card>
        <ModelResponses astronautId={state?.astronaut_id ?? form.astronaut_id} running={!!state?.running} />
        <Card title="Alerts raised during replay">
          <div className="col" style={{ maxHeight: 420, overflowY: "auto" }}>
            {alerts.length === 0 && <div className="empty">No alerts yet</div>}
            {alerts.map((a) => <AlertItem key={a.id} a={a} showWho={a.astronaut_id ?? "Habitat"} />)}
          </div>
        </Card>
        <Card title="Incoming readings" className="span2" extra={<span className="small faint">newest first</span>}>
          <div className="table-wrap" style={{ maxHeight: 300, overflowY: "auto" }}>
            <table className="tbl">
              <thead><tr><th>Time (sim)</th><th>Source</th><th>Metric</th><th>Value</th></tr></thead>
              <tbody>{feed.map((f, i) => <tr key={i}><td className="mono small">{f.timestamp.slice(5, 16).replace("T", " ")}</td><td className="small">{f.astronaut_id ?? "habitat"}</td><td>{METRIC_LABEL[f.metric] ?? f.metric}</td><td className="mono">{fmt(f.value, 2)} {f.unit}</td></tr>)}</tbody>
            </table>
          </div>
        </Card>
      </div>
    </>
  );
}

const RANK: Record<string, number> = { none: 0, info: 1, caution: 2, warning: 3 };

/** Latest output of every model for the simulated astronaut; refreshes while the simulator runs. */
function ModelResponses({ astronautId, running }: { astronautId: string; running: boolean }) {
  const res = useApi<{ assessments: any[] }>(`/ai/astronauts/${astronautId}/assessments`);
  useEffect(() => { if (!running) return; const t = setInterval(res.reload, 5000); return () => clearInterval(t); }, [running, res.reload]);
  const rows = [...(res.data?.assessments ?? [])].sort((a, b) => (RANK[b.severity] ?? 0) - (RANK[a.severity] ?? 0));
  return (
    <Card title="Model responses" className="span2" extra={<span className="small faint">{astronautId} · runs at the end of each simulated day</span>}>
      {rows.length === 0 && <div className="empty">Start a scenario; models run after each simulated day.</div>}
      <div className="table-wrap"><table className="tbl">
        <thead><tr><th>Model</th><th>Result</th><th>Why</th><th>Data</th></tr></thead>
        <tbody>{rows.map((a) => (
          <tr key={a.model_id}>
            <td><b>{a.model_id}</b></td>
            <td>{a.status === "ok" ? <Badge kind={a.severity === "none" ? "ok" : a.severity}>{a.score_label || a.severity}</Badge> : <Badge kind="neutral">{a.status.replace("_", " ")}</Badge>}</td>
            <td className="small">{a.explanation}</td>
            <td><Badge kind="sim">simulated</Badge></td>
          </tr>
        ))}</tbody>
      </table></div>
    </Card>
  );
}
