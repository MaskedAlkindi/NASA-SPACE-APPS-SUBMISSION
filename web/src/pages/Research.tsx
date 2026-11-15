import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CartesianGrid, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { isCrewWide, useAuth } from "../auth";
import { Badge, Card, chartTooltip, DataClassBadge, fmt, Loading } from "../components/ui";
import { useApi } from "../hooks";

const TP_ORDER = ["L-92", "L-44", "L-3", "R+1", "R+45", "R+82", "R+194"];
const COLORS = ["#005c96", "#1d2bdb", "#d81b1b", "#b86e00"];

function AnalyteExplorer({ accession }: { accession: string }) {
  const obs = useApi<any>(`/research/datasets/${accession}/observations`);
  const analytes: string[] = obs.data?.analytes ?? [];
  const [analyte, setAnalyte] = useState<string | null>(null);
  const a = analyte ?? (analytes.includes("WHITE BLOOD CELL COUNT") ? "WHITE BLOOD CELL COUNT" : analytes.includes("GLUCOSE") ? "GLUCOSE" : analytes[0]);
  const { rows, subjects, unit, range } = useMemo(() => {
    const items = (obs.data?.items ?? []).filter((i: any) => i.analyte === a);
    const subjects = [...new Set(items.map((i: any) => i.subject_id))].sort() as string[];
    const tps = [...new Set(items.map((i: any) => i.timepoint))].sort((x: any, y: any) => TP_ORDER.indexOf(x) - TP_ORDER.indexOf(y)) as string[];
    const rows = tps.map((tp) => ({ tp, ...Object.fromEntries(items.filter((i: any) => i.timepoint === tp).map((i: any) => [i.subject_id, i.value])) }));
    const withRange = items.find((i: any) => i.range_min != null);
    return { rows, subjects, unit: items[0]?.unit ?? "", range: withRange ? [withRange.range_min, withRange.range_max] : null };
  }, [obs.data, a]);
  if (!obs.data) return <Loading />;
  return (
    <div className="col">
      <div className="row">
        <select className="input" value={a} onChange={(e) => setAnalyte(e.target.value)}>{analytes.map((x) => <option key={x}>{x}</option>)}</select>
        <span className="small muted">{unit} · {subjects.length} crew · shaded = lab reference range{range ? ` (${range[0]}–${range[1]})` : " (n/a)"}</span>
      </div>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={rows} margin={{ top: 6, right: 8, left: -6, bottom: 0 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="tp" />
          <YAxis domain={["auto", "auto"]} />
          <Tooltip {...chartTooltip} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          {range && <ReferenceArea y1={range[0]} y2={range[1]} fill="#6c9cff" fillOpacity={0.07} />}
          <ReferenceArea x1="L-3" x2="R+1" fill="#6b4fbb" fillOpacity={0.06} label={{ value: "flight", fill: "#6b4fbb", fontSize: 10 }} />
          {subjects.map((s, i) => <Line key={s} dataKey={s} stroke={COLORS[i % 4]} strokeWidth={2} dot={{ r: 3 }} connectNulls />)}
        </LineChart>
      </ResponsiveContainer>
      <div className="small faint">L-n = days before launch, R+n = days after return. Values plotted exactly as published; no imputation.</div>
    </div>
  );
}

export default function Research() {
  const { user } = useAuth();
  const ds = useApi<any>("/research/datasets");
  const fs = useApi<any>("/research/findings");
  const [tab, setTab] = useState<"imported" | "discovered">("imported");
  const [importing, setImporting] = useState<string | null>(null);
  const datasets = ds.data?.datasets ?? [];
  const imported = datasets.filter((d: any) => d.status === "downloaded");
  const discovered = datasets.filter((d: any) => d.status !== "downloaded");
  const [open, setOpen] = useState<string | null>(null);

  const reimport = async () => {
    setImporting("Importing…");
    try { const r = await api<any>("/research/import?refresh=true", { method: "POST" }); setImporting(`Imported ${r.datasets} datasets, ${r.observations} observations (origin: ${r.origins.join(", ") || "n/a"})${r.errors.length ? ` · ${r.errors.length} issues` : ""}`); ds.reload(); fs.reload(); }
    catch (e: any) { setImporting(`Import failed: ${e.message}`); }
  };
  const computed = (fs.data?.findings ?? []).filter((f: any) => f.evidence_type === "computed_from_dataset");
  const facts = (fs.data?.findings ?? []).filter((f: any) => f.evidence_type === "nasa_report_fact");

  return (
    <>
      <div className="page-head">
        <div><h1>NASA research</h1><p>Public data from the NASA Open Science Data Repository (OSDR) plus curated NASA Human Research Program context.</p></div>
        <div className="spacer" />
        <span className="row small"><span className={`dot ${ds.data?.module_status?.state === "connected" ? "on" : "warn"}`} />{ds.data?.module_status?.detail}</span>
        {isCrewWide(user) && <button className="btn" onClick={reimport}>Refresh from OSDR</button>}
      </div>
      {importing && <div className="small muted">{importing}</div>}
      <div className="banner" style={{ borderColor: "var(--research)" }}>
        <DataClassBadge value="research" /> This data comes from the Inspiration4 crew (4 people, 3-day flight), <b>not</b> the demo crew. It is used for scientific context in explanations, not to train HEALTH-01’s wearable models (it contains no heart-rate, HRV or sleep data).
      </div>

      <div className="grid g2">
        <Card title="Inspiration4 crew lab explorer" extra={<div className="tabs">{imported.map((d: any) => <button key={d.accession} className={(open ?? imported[0]?.accession) === d.accession ? "on" : ""} onClick={() => setOpen(d.accession)}>{d.accession}</button>)}</div>}>
          {imported.length ? <AnalyteExplorer accession={open ?? imported[0].accession} /> : <div className="empty">No downloaded datasets yet</div>}
        </Card>
        <Card title="Findings computed from NASA data" extra={<Badge kind="research">descriptive · n=4</Badge>}>
          <div className="col" style={{ maxHeight: 330, overflowY: "auto" }}>
            {computed.map((f: any) => (
              <div key={f.id} className="tile">
                <div style={{ fontWeight: 600 }}>{f.title}</div>
                <div className="small muted">{f.summary}</div>
                <div className="small faint">Per crew: {f.stats.per_subject?.map((s: any) => `${s.subject} ${s.pct > 0 ? "+" : ""}${s.pct}%`).join(" · ")}</div>
              </div>
            ))}
            {computed.length > 0 && <div className="small faint">Caveat: {computed[0].caveats}</div>}
          </div>
        </Card>
      </div>

      <Card title="Datasets" extra={<div className="tabs"><button className={tab === "imported" ? "on" : ""} onClick={() => setTab("imported")}>Imported ({imported.length})</button><button className={tab === "discovered" ? "on" : ""} onClick={() => setTab("discovered")}>Discovered metadata ({discovered.length})</button></div>}>
        {!ds.data ? <Loading /> : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Accession</th><th>Title</th><th>Organism</th><th>Mission / type</th><th>Status</th><th>Provenance</th></tr></thead>
              <tbody>
                {(tab === "imported" ? imported : discovered).map((d: any) => (
                  <tr key={d.accession}>
                    <td className="mono"><a href={d.source_url} target="_blank" rel="noreferrer">{d.accession}</a></td>
                    <td style={{ maxWidth: 460 }}>
                      <div style={{ fontWeight: 550 }}>{d.title}</div>
                      <div className="small faint">{d.relevance}</div>
                      {tab === "imported" && <details className="small muted"><summary style={{ cursor: "pointer" }}>Study description & files</summary><p>{d.description}</p>
                        <div>Downloaded: {d.extra?.downloaded?.map((x: any) => `${x.file} (${x.rows} rows, ${x.origin})`).join("; ")}</div>
                        <div>Release date: {d.release_date} · Mission dates: {d.extra?.mission_start}–{d.extra?.mission_end}</div></details>}
                    </td>
                    <td className="small">{d.organism || "—"}</td>
                    <td className="small">{d.mission || "—"}<div className="faint">{d.project_type}</div></td>
                    <td><Badge kind={d.status === "downloaded" ? "research" : "neutral"}>{d.status.replace("_", " ")}</Badge>{d.observations > 0 && <div className="small faint">{fmt(d.observations, 0)} obs.</div>}</td>
                    <td className="small faint" style={{ maxWidth: 260 }}>{d.doi && <div>DOI <a href={`https://doi.org/${d.doi}`} target="_blank" rel="noreferrer">{d.doi}</a></div>}{d.citation && <div>{d.citation.slice(0, 110)}…</div>}<div>{d.license.slice(0, 80)}…</div></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <h2>Facts from the NASA reports linked in the challenge resources <span className="small faint">(each quote checked against the report; see the <Link to="/risks">Hazards &amp; Risks</Link> page for the full map)</span></h2>
      <div className="grid g3">
        {facts.map((f: any) => (
          <Card key={f.id} title={<h2 style={{ fontSize: 16 }}>{f.title}</h2>} extra={<Badge kind="research">{f.stats.page ? `p. ${f.stats.page}` : "web"}</Badge>}>
            <div className="small faint">{f.caveats} · <a href={f.source_url} target="_blank" rel="noreferrer">{f.stats.source}</a></div>
          </Card>
        ))}
      </div>
    </>
  );
}
