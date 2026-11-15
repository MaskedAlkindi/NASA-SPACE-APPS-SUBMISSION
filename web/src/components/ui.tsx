import { Fragment, type ReactNode } from "react";
import type { Alert, MetricSummary } from "../api";
import { METRIC_LABEL } from "../api";

export function Card({ title, extra, children, className = "" }: { title?: ReactNode; extra?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || extra) && (
        <div className="card-head">
          {typeof title === "string" ? <h2>{title}</h2> : title}
          <div className="spacer" />
          {extra}
        </div>
      )}
      {children}
    </section>
  );
}

export function Badge({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`badge ${kind}`}>{children}</span>;
}

export function DataClassBadge({ value }: { value?: string }) {
  if (!value) return null;
  const kind = value === "simulated" ? "sim" : value === "research" ? "research" : "real";
  const label = value === "simulated" ? "SIMULATED" : value === "research" ? "NASA RESEARCH" : "REAL DEVICE";
  return <Badge kind={kind}>{label}</Badge>;
}

export const STATUS_TEXT: Record<string, string> = {
  within_usual_range: "usual range", above_usual_range: "above usual", below_usual_range: "below usual", no_data: "no data",
};

export function fmt(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (Math.abs(v) >= 1000) return Math.round(v).toLocaleString();
  return Number.isInteger(v) ? String(v) : v.toFixed(digits);
}

export function MetricTile({ m }: { m: MetricSummary }) {
  const delta = m.delta_vs_baseline_pct;
  return (
    <div className={`tile ${m.concern ? "concern" : ""}`}>
      <div className="label"><span>{m.label}</span>{m.status !== "no_data" && <Badge kind={m.concern ? "caution" : "neutral"}>{STATUS_TEXT[m.status]}</Badge>}</div>
      <div className="value">{fmt(m.latest)}<span className="unit">{m.unit}</span></div>
      <div className="sub">
        {m.status === "no_data" ? "not available" : <>7d avg {fmt(m.avg_7d)} · usual {fmt(m.baseline_median)}{delta != null && <> · {delta > 0 ? "+" : ""}{delta}%</>}</>}
      </div>
    </div>
  );
}

export function AlertItem({ a, onAck, showWho }: { a: Alert; onAck?: (id: number) => void; showWho?: string }) {
  return (
    <div className={`alert-item ${a.severity}`}>
      <div className="row">
        <Badge kind={a.severity}>{a.severity.toUpperCase()}</Badge>
        <span className="title">{a.title}</span>
        <span className="spacer" style={{ flex: 1 }} />
        {showWho && <span className="small muted">{showWho}</span>}
        <span className="small faint">{new Date(a.observed_at).toLocaleDateString()}</span>
      </div>
      <div className="small">{a.message}</div>
      {a.evidence?.length > 0 && (
        <div className="evidence">
          {a.evidence.map((e, i) => (
            <span key={i}>
              {METRIC_LABEL[e.metric] ?? e.metric}: {fmt(e.value)} {e.unit}
              {e.baseline_median !== undefined && <> · usual {fmt(e.baseline_median)}</>}
              {e.z !== undefined && <> · z={fmt(e.z, 1)}</>}
              {e.note && <> · {e.note}</>}
            </span>
          ))}
        </div>
      )}
      {a.recommendation && <div className="small muted">↳ {a.recommendation}</div>}
      <div className="row small faint">
        <span>source: {a.source.startsWith("rule") ? `threshold ${a.source}` : `model ${a.source}`}</span>
        <DataClassBadge value={a.data_class} />
        {onAck && !a.acknowledged && <button className="btn ghost small" style={{ marginLeft: "auto", padding: "2px 10px" }} onClick={() => onAck(a.id)}>Acknowledge</button>}
      </div>
    </div>
  );
}

/** Minimal, safe markdown: **bold**, _italic_, bullets, line breaks. Text is escaped by React. */
export function Markdown({ text }: { text: string }) {
  const inline = (s: string) => {
    const parts = s.split(/(\*\*[^*]+\*\*|_[^_]+_|\[R\d+\])/g);
    return parts.map((p, i) => {
      if (p.startsWith("**") && p.endsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
      if (p.startsWith("_") && p.endsWith("_") && p.length > 2) return <em key={i} className="muted">{p.slice(1, -1)}</em>;
      if (/^\[R\d+\]$/.test(p)) return <span key={i} className="badge research" style={{ padding: "0 5px" }}>{p.slice(1, -1)}</span>;
      return <Fragment key={i}>{p}</Fragment>;
    });
  };
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) blocks.push(<ul key={blocks.length}>{list.map((l, i) => <li key={i}>{inline(l)}</li>)}</ul>);
    list = [];
  };
  text.split("\n").forEach((line) => {
    const t = line.trim();
    if (/^[-*•] /.test(t)) { list.push(t.slice(2)); return; }
    flush();
    if (t) blocks.push(<p key={blocks.length}>{inline(t.replace(/^#+\s*/, ""))}</p>);
  });
  flush();
  return <div className="md">{blocks}</div>;
}

export function Loading({ what = "Loading" }: { what?: string }) {
  return <div className="empty">{what}…</div>;
}

export const chartTooltip = {
  contentStyle: { background: "#ffffff", border: "1px solid #17191f", borderRadius: 10, fontSize: 12 },
  labelStyle: { color: "#858d9c" },
};
