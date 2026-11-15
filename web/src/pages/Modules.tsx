import { Link, useSearchParams } from "react-router-dom";
import { METRIC_LABEL } from "../api";
import { Badge, Card, DataClassBadge, Loading } from "../components/ui";
import { useApi } from "../hooks";

const STATE_KIND: Record<string, string> = { connected: "ok", running: "ok", available: "info", integrated: "ok", waiting: "caution", degraded: "caution", unavailable: "warning" };
const PHONE_MODULES = new Set(["apple_health", "android_health"]);

export default function Modules() {
  const mods = useApi<any>("/modules");
  const [params] = useSearchParams();
  const astronaut = params.get("a");
  const devicesTo = astronaut ? `/devices?a=${encodeURIComponent(astronaut)}` : "/devices";
  if (!mods.data) return <Loading />;
  return (
    <>
      <div className="page-head">
        <div><h1>Modules & integrations</h1><p>Every integration implements the same contract (ID, version, metrics, config, ingest, validate, status) and can fail without affecting the others.</p></div>
      </div>
      <div className="grid g3">
        {mods.data.modules.map((m: any) => {
          const phone = PHONE_MODULES.has(m.id) && m.status?.state === "waiting";
          const state = phone ? "integrated" : m.status?.state;
          return (
          <Card key={m.id} title={<div><h2>{m.name ?? m.id}</h2><div className="small faint mono">{m.id} · v{m.version ?? "?"} · {m.category}</div></div>}
            extra={<Badge kind={STATE_KIND[state] ?? "neutral"}>{state}</Badge>}>
            <div className="small muted">{m.description}</div>
            <div className="small" style={{ margin: "8px 0" }}><span className="faint">Status:</span> {phone ? <>Integrated. Go to the <Link to={devicesTo}>Devices</Link> page to assign a phone.</> : m.status?.detail}</div>
            {m.data_class && <div className="row small"><span className="faint">Data class</span><DataClassBadge value={m.data_class} />{m.accepts_ingest === false && <Badge kind="neutral">read-only source</Badge>}</div>}
            {m.ingest?.count > 0 && <div className="small faint" style={{ marginTop: 6 }}>{m.ingest.count.toLocaleString()} measurements · last {new Date(m.ingest.last_timestamp).toLocaleString()}</div>}
            {m.supported_metrics?.length > 0 && (
              <div className="evidence" style={{ marginTop: 10 }}>{m.supported_metrics.map((x: string) => <span key={x}>{METRIC_LABEL[x] ?? x}</span>)}</div>
            )}
            {m.config && (
              <details className="small" style={{ marginTop: 10 }}>
                <summary className="muted" style={{ cursor: "pointer" }}>Configuration</summary>
                <pre className="mono small" style={{ whiteSpace: "pre-wrap", color: "var(--muted)", maxHeight: 220, overflow: "auto" }}>{JSON.stringify(m.config, null, 2)}</pre>
              </details>
            )}
          </Card>
          );
        })}
      </div>
      <Card title="Shared measurement schema (metric catalog)">
        <div className="table-wrap">
          <table className="tbl">
            <thead><tr><th>Metric</th><th>Label</th><th>Unit</th><th>Domain</th><th>Valid range</th><th>Daily aggregation</th><th>Scope</th></tr></thead>
            <tbody>{mods.data.metrics.map((m: any) => (
              <tr key={m.name}><td className="mono">{m.name}</td><td>{m.label}</td><td className="mono">{m.unit}</td><td>{m.domain}</td><td className="mono">{m.min} – {m.max}</td><td>{m.daily}</td><td>{m.per_astronaut ? "astronaut" : "habitat"}</td></tr>
            ))}</tbody>
          </table>
        </div>
        <div className="small faint" style={{ marginTop: 8 }}>Every stored measurement carries: astronaut ID, metric, value (numeric or structured), unit, timestamp, source device, source module, quality and data class (real / research / simulated).</div>
      </Card>
    </>
  );
}
