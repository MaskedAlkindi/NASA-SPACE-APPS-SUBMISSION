import { useMemo, useState } from "react";
import { AstronautPicker, useSelectedAstronaut } from "../components/AstronautPicker";
import { Badge, Card, fmt, Loading } from "../components/ui";
import { useApi, useLive } from "../hooks";

const STATUS: Record<string, { label: string; kind: string }> = {
  attention: { label: "needs attention", kind: "warning" },
  watch: { label: "watch", kind: "caution" },
  ok: { label: "OK", kind: "ok" },
  no_data: { label: "no data yet", kind: "neutral" },
  clinical_exam: { label: "needs a clinical exam", kind: "info" },
  not_monitored: { label: "not monitored", kind: "neutral" },
};
const MONITORING: Record<string, string> = {
  direct: "measured by this tool", partial: "partly covered by related indicators",
  clinical: "needs an exam the tool cannot do", none: "operational risk, outside personal monitoring",
};

function Evidence({ items }: { items: any[] }) {
  if (!items.length) return null;
  return (
    <div className="col" style={{ gap: 6 }}>
      <h3>Evidence from the challenge resources</h3>
      {items.map((e) => (
        <div key={e.id} className="small" style={{ borderLeft: "3px solid var(--steel)", paddingLeft: 10 }}>
          {e.statement}{" "}
          <a href={e.url} target="_blank" rel="noreferrer">{e.source}{e.page ? `, p. ${e.page}` : ""}</a>
          <div className="faint" style={{ fontStyle: "italic" }}>“{e.quote}”</div>
        </div>
      ))}
    </div>
  );
}

function Models({ models }: { models: any }) {
  const r = models.radiation, b = models.bone, m = models.body_mass;
  if (!r && !b && !m) return null;
  return (
    <div className="grid g3" style={{ gap: 10 }}>
      {r && <div className="tile"><div className="label">Cumulative dose (estimate)</div>
        <div className="value">{fmt(r.cumulative_mGy)}<span className="unit">mGy</span></div>
        <div className="sub">NASA reference for this mission length: {r.nasa_reference_mGy_for_this_duration.join("–")} mGy · mean {r.mean_rate_uGy_h} µGy/h</div></div>}
      {b && <div className="tile"><div className="label">Expected bone-density loss</div>
        <div className="value">{b.expected_loss_pct.join("–")}<span className="unit">%</span></div>
        <div className="sub">{b.mission_months} months × NASA 1–1.5%/month · exercise adherence (14 d): {b.exercise_adherence_14d_pct ?? "—"}%</div></div>}
      {m && <div className="tile"><div className="label">Body-mass change</div>
        <div className="value">{m.change_pct > 0 ? "+" : ""}{m.change_pct}<span className="unit">%</span></div>
        <div className="sub">{m.start_kg} → {m.now_kg} kg over {m.days} d · NASA average {m.nasa_average_change_pct}%</div></div>}
    </div>
  );
}

export default function Risks() {
  const { crew, selected, select, current } = useSelectedAstronaut();
  const view = useApi<any>(selected ? `/astronauts/${selected}/risks` : null);
  const ch = useApi<any>("/challenge");
  const [hazard, setHazard] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useLive((e) => { if (e.type === "alert" && (e.alert.astronaut_id === selected || e.alert.astronaut_id === null)) view.reload(); });

  const risks = useMemo(() => (view.data?.risks ?? []).filter((r: any) => !hazard || r.hazards.includes(hazard)), [view.data, hazard]);
  const counts = view.data?.counts;

  return (
    <>
      <div className="page-head">
        <div><h1>NASA hazards &amp; risks{current ? ` · ${current.callsign}` : ""}</h1>
          <p>Built from the official challenge resources: NASA's five hazards of human spaceflight, the 17 Human Research Program risks, and facts checked against NASA reports.</p></div>
        <div className="spacer" />
        <AstronautPicker crew={crew} selected={selected} onSelect={select} />
      </div>

      {ch.data && (
        <Card title="Health indicators named in the challenge">
          <div className="row">
            {ch.data.indicator_coverage.map((c: any) => (
              <Badge key={c.indicator} kind={c.supported ? "ok" : "warning"}>{c.supported ? "✓" : "✗"} {c.indicator}</Badge>
            ))}
          </div>
        </Card>
      )}

      <div className="grid g-auto">
        {(ch.data?.hazards ?? []).map((h: any) => {
          const name = h.name.replace("Distance From Earth", "Distance from Earth");
          const on = hazard === name;
          return (
            <button key={h.slug} className="card" onClick={() => setHazard(on ? null : name)}
              style={{ textAlign: "left", cursor: "pointer", outline: on ? "3px solid var(--accent2)" : undefined, font: "inherit" }}>
              <h2>{name}</h2>
              <p className="small muted" style={{ margin: "6px 0" }}>{h.summary.slice(0, 190)}…</p>
              <span className="small">{on ? "Showing related risks · click to clear" : "Show related risks"}</span>
            </button>
          );
        })}
      </div>

      {!view.data ? <Loading what="Assessing risks" /> : (
        <>
          <div className="row">
            {counts && Object.entries(counts).filter(([, n]) => (n as number) > 0).map(([s, n]) => <Badge key={s} kind={STATUS[s].kind}>{n as number} {STATUS[s].label}</Badge>)}
            <span className="small faint">Mission day {view.data.mission_day}. {view.data.disclaimer}</span>
          </div>
          <div className="col" style={{ gap: 12 }}>
            {risks.map((r: any) => {
              const st = STATUS[r.status];
              const isOpen = open === r.slug;
              return (
                <Card key={r.slug} title={<div><h2>{r.name}</h2><div className="small faint">{r.category} · {r.hazards.join(" · ")}</div></div>}
                  extra={<><Badge kind={st.kind}>{st.label}</Badge><button className="btn ghost" style={{ padding: "3px 10px" }} onClick={() => setOpen(isOpen ? null : r.slug)}>{isOpen ? "Less" : "Details"}</button></>}>
                  <div className="col">
                    <div className="small muted">Coverage: {MONITORING[r.monitoring]}.{r.note ? ` ${r.note}` : ""}</div>
                    {r.indicators.length > 0 && (
                      <div className="evidence">
                        {r.indicators.map((i: any) => (
                          <span key={i.metric} style={{ borderColor: i.concern ? "var(--caution)" : undefined, color: i.concern ? "var(--caution)" : undefined }}>
                            {i.label}: {i.latest == null ? "no data" : `${fmt(i.latest)} ${i.unit}`}{i.usual != null ? ` (usual ${fmt(i.usual)})` : ""}
                          </span>
                        ))}
                      </div>
                    )}
                    {r.alerts.length > 0 && <div className="small">Recent alerts: {r.alerts.map((a: any) => <Badge key={a.id} kind={a.severity}>{a.title}</Badge>)}</div>}
                    <Models models={r.models} />
                    {r.what_can_be_done && (
                      <div className="small" style={{ background: "var(--sunk)", padding: "8px 12px", borderRadius: 8 }}>
                        <b>What NASA says can be done:</b> {r.what_can_be_done} <a href={r.url} target="_blank" rel="noreferrer">NASA HRP</a>
                      </div>
                    )}
                    {isOpen && (
                      <>
                        {r.top_risks && <div className="small"><b>The risk:</b> {r.top_risks}</div>}
                        {r.did_you_know && <div className="small muted"><b>Did you know?</b> {r.did_you_know}</div>}
                        {r.formal_description && <div className="small faint">Formal risk description: {r.formal_description}</div>}
                        <Evidence items={r.evidence} />
                      </>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        </>
      )}

      {ch.data && (
        <Card title="Where this comes from">
          <p className="small muted" style={{ marginTop: 0 }}>{ch.data.datasets_note} Snapshot taken {ch.data.generated_at.slice(0, 10)} from the <a href={ch.data.resources_tab} target="_blank" rel="noreferrer">challenge Resources tab</a>.</p>
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Resource</th><th>Agency</th><th>Status</th><th>Used for</th></tr></thead>
              <tbody>
                {ch.data.resources.map((r: any) => (
                  <tr key={r.id}><td><a href={r.url} target="_blank" rel="noreferrer">{r.title}</a></td><td>{r.agency}</td><td><Badge kind="ok">{r.status}</Badge></td>
                    <td className="small muted">{r.id === "nasa-hrp-hazards" ? "the five hazards above" : r.id === "nasa-hrp-risks" ? "the 17 risks, their guidance and linked reports" : r.id === "nasa-hrp-ongoing" ? "study descriptions (Standard Measures, CIPHER…)" : "radiation context and facts"}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
          <h3 style={{ margin: "14px 0 6px" }}>NASA reports downloaded and parsed ({ch.data.documents.length})</h3>
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Document</th><th>Pages</th><th>Size</th></tr></thead>
              <tbody>{ch.data.documents.map((d: any) => (
                <tr key={d.file}><td><a href={d.url} target="_blank" rel="noreferrer">{d.file}</a></td><td className="mono">{d.pages}</td><td className="mono">{(d.bytes / 1e6).toFixed(1)} MB</td></tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
      )}
    </>
  );
}
