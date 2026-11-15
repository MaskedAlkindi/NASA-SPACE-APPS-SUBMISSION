import { Link } from "react-router-dom";
import { api, type Alert, type CrewMember } from "../api";
import { useApi, useLive } from "../hooks";
import { useAuth } from "../auth";
import { canSeeDashboard } from "../components/Layout";
import { AlertItem, Badge, Card, DataClassBadge, fmt, Loading, STATUS_TEXT } from "../components/ui";

const DOMAIN_LABEL: Record<string, string> = { cardiovascular: "Cardio", sleep: "Sleep", activity: "Activity", wellbeing: "Wellbeing", vitals: "Vitals" };

export default function Overview() {
  const { user } = useAuth();
  const mission = useApi<any>("/mission");
  const crew = useApi<{ astronauts: CrewMember[] }>("/astronauts");
  const env = useApi<any>("/environment?hours=24");
  const modules = useApi<any>("/modules");
  useLive((e) => {
    if (e.type === "alert") { mission.reload(); crew.reload(); }
    if (e.type === "measurements" && e.items.some((i) => i.metric.startsWith("cabin_") || i.metric === "radiation_dose_rate")) env.reload();
  });

  const m = mission.data;
  if (!m) return <Loading what="Loading mission" />;
  const names: Record<string, string> = Object.fromEntries((crew.data?.astronauts ?? []).map((c) => [c.id, c.callsign]));
  const ack = async (id: number) => { await api(`/alerts/${id}/acknowledge`, { method: "POST" }); mission.reload(); crew.reload(); };
  const mods = modules.data?.modules ?? [];
  const up = mods.filter((x: any) => ["connected", "available", "running"].includes(x.status?.state)).length;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{m.name}</h1>
          <p>{m.vehicle} · started {m.start_date}</p>
        </div>
        <div className="spacer" />
        <DataClassBadge value={m.data_class} />
        {m.sim_running && <Badge kind="sim">SIMULATOR RUNNING</Badge>}
      </div>
      <div className="banner">All crew members, measurements and environmental readings in this demo mission are <b>simulated</b>. NASA research data is under Settings › NASA research.</div>

      <div className="grid g4">
        <div className="tile"><div className="label">Mission day</div><div className="value">{m.mission_day}<span className="unit">/ {m.planned_duration_days}</span></div>
          <div className="progress" style={{ marginTop: 8 }}><div style={{ width: `${Math.min(100, (m.mission_day / m.planned_duration_days) * 100)}%` }} /></div></div>
        <div className="tile"><div className="label">Crew monitored</div><div className="value">{m.visible_crew.length}<span className="unit">/ {m.crew_count}</span></div><div className="sub">wearables + daily check-ins</div></div>
        <div className="tile"><div className="label">Active alerts</div><div className="value" style={{ color: m.alert_counts.warning ? "var(--warning)" : undefined }}>{m.alert_counts.warning + m.alert_counts.caution}</div>
          <div className="sub">{m.alert_counts.warning} warning · {m.alert_counts.caution} caution · {m.alert_counts.info} info</div></div>
        <div className="tile"><div className="label">Monitoring modules</div><div className="value">{up}<span className="unit">/ {mods.length} online</span></div><div className="sub"><Link to="/modules">view integrations →</Link></div></div>
      </div>

      <div className="grid g-auto">
        {(crew.data?.astronauts ?? []).map((c) => (
          <Link key={c.id} to={canSeeDashboard(user?.role) ? `/dashboard?a=${c.id}` : "#"} onClick={(e) => { if (!canSeeDashboard(user?.role)) e.preventDefault(); }}
            style={{ textDecoration: "none", color: "inherit", cursor: canSeeDashboard(user?.role) ? "pointer" : "default" }}>
            <Card title={<div><h2>{c.callsign}</h2><div className="small muted">{c.role} {c.data_class === "simulated" && <Badge kind="sim">simulated</Badge>}</div></div>}
              extra={c.open_alerts > 0 ? <Badge kind="caution">{c.open_alerts} alerts</Badge> : <Badge kind="ok">nominal</Badge>}>
              <div className="grid g2" style={{ gap: 8 }}>
                {[["resting_heart_rate", "Resting HR"], ["hrv_sdnn", "HRV"], ["sleep_duration", "Sleep"], ["fatigue_score", "Fatigue"]].map(([k, label]) => {
                  const v = c.key_metrics[k];
                  return (
                    <div key={k} className="tile" style={{ padding: "8px 10px" }}>
                      <div className="label">{label}</div>
                      <div style={{ fontWeight: 650, fontSize: 17 }}>{v ? fmt(v.latest) : "—"}<span className="unit">{v?.unit}</span></div>
                      <div className="sub" style={{ color: v && v.status !== "within_usual_range" ? "var(--caution)" : undefined }}>{v ? STATUS_TEXT[v.status] : "no data"}</div>
                    </div>
                  );
                })}
              </div>
              <div className="row small" style={{ marginTop: 10 }}>
                {Object.entries(c.domain_status).map(([d, s]) => (
                  <span key={d} className="row" style={{ gap: 4 }}><span className={`dot ${s === "attention" ? "warn" : s === "nominal" ? "on" : ""}`} />{DOMAIN_LABEL[d] ?? d}</span>
                ))}
              </div>
            </Card>
          </Link>
        ))}
      </div>

      <div className="grid g3">
        <Card title="Active alerts" className="span2" extra={<span className="small faint">click Acknowledge once reviewed</span>}>
          <div className="col">
            {m.active_alerts.length === 0 && <div className="empty">No active alerts</div>}
            {m.active_alerts.slice(0, 8).map((a: Alert) => <AlertItem key={a.id} a={a} onAck={ack} showWho={a.astronaut_id ? names[a.astronaut_id] : "Habitat"} />)}
          </div>
        </Card>
        <Card title="Habitat environment" extra={<DataClassBadge value={env.data?.summary?.metrics?.[0]?.data_class} />}>
          <div className="col" style={{ gap: 8 }}>
            {(env.data?.summary?.metrics ?? []).map((e: any) => (
              <div key={e.metric} className="tile" style={{ padding: "8px 12px" }}>
                <div className="label"><span>{e.label}</span><span className="faint">24h max {fmt(e.max_24h, 2)}</span></div>
                <div style={{ fontWeight: 650, fontSize: 18 }}>{fmt(e.latest, 2)}<span className="unit">{e.unit}</span></div>
              </div>
            ))}
            {!env.data?.summary?.metrics?.length && <div className="empty">No environment data</div>}
          </div>
        </Card>
      </div>
    </>
  );
}
