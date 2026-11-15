import { useState } from "react";
import { api } from "../api";
import { isCrewWide, useAuth } from "../auth";
import { AstronautPicker, useSelectedAstronaut } from "../components/AstronautPicker";
import { Badge, Card, fmt, Loading } from "../components/ui";
import { useApi } from "../hooks";

const EVIDENCE: Record<string, { label: string; kind: string }> = {
  earth_research: { label: "Earth research data", kind: "research" },
  simulation: { label: "Simulated data", kind: "sim" },
  rule_based: { label: "Rule-based", kind: "info" },
  spaceflight: { label: "Spaceflight data", kind: "ok" },
};
const SEV: Record<string, string> = { warning: "warning", caution: "caution", info: "info", none: "neutral" };

function Metrics({ m }: { m: any }) {
  const r = m.report;
  if (!r) return <div className="small faint">No evaluation report.</div>;
  const rows: [string, string][] = [];
  if (m.id === "illness_rhr" && r.held_out_half) {
    const h = r.held_out_half;
    rows.push(["Sensitivity (held-out)", `${fmt(h.sensitivity * 100, 0)}% of ${h.events_evaluable} illness events`],
      ["Day-level specificity", `${fmt(h.specificity_day * 100, 1)}%`],
      ["False alerts", `${h.false_alert_episodes_per_30_healthy_days} per 30 healthy days`],
      ["Median alert vs symptom onset", `${h.median_days_alert_vs_onset} days`]);
  }
  if (m.id === "fatigue_pmdata" && r.deployed) {
    rows.push(["Tired-day AUC (LOSO)", `${r.deployed.tired.loso.auc_pooled} (within-person ${r.deployed.tired.loso.auc_within_person_median})`],
      ["Stressed-day AUC (LOSO)", `${r.deployed.stressed.loso.auc_pooled}`],
      ["Yesterday's self-report alone", `${r.results.tired["baseline/yesterday_report"].auc_pooled}`]);
  }
  if (m.id === "glucose_metabolic" && r.insulin_resistance_from_cgm) {
    rows.push(["Insulin-resistance flag from CGM (LOSO AUC)", `${r.insulin_resistance_from_cgm.auc} (95% CI ${r.insulin_resistance_from_cgm.auc_95ci_bootstrap.join("–")})`],
      ["Post-meal rise MAE", `${r.postprandial_rise.mae_mg_dl_model} mg/dL (carbs-only ${r.postprandial_rise.mae_mg_dl_carbs_only_linear})`],
      ["HOMA-IR median by group", Object.entries(r.homa_ir.by_group_median).map(([g, v]) => `${g} ${v}`).join(", ")]);
  }
  if (m.id === "sleep_hrv" && r.hr_from_rr_vs_actigraph) {
    rows.push(["HR from RR vs device", `MAE ${r.hr_from_rr_vs_actigraph.median_mae_bpm} bpm, r ${r.hr_from_rr_vs_actigraph.median_r}`],
      ["Sleep efficiency formula", `max difference ${r.sleep_efficiency_recomputed.max_abs_diff_pct_points} points`]);
  }
  if (m.id === "orthostatic" && r.agreement_with_published_sit2stand_change) {
    const a = r.agreement_with_published_sit2stand_change.seg_delta_sbp;
    rows.push(["SBP change vs published", `r ${a.pearson_r}, mean |diff| ${a.mean_abs_diff_mmHg} mmHg (moderate)`]);
  }
  if (m.id === "legacy_anomaly" && r.model) rows.push(["Simulated test AUC", `${r.model.roc_auc}`]);
  if (m.id === "legacy_fatigue_sim" && r.model) rows.push(["Simulated test MAE", `${r.model.mae}`]);
  if (!rows.length) return <div className="small faint">Report available via the API.</div>;
  return <table className="tbl"><tbody>{rows.map(([k, v]) => <tr key={k}><td className="muted">{k}</td><td className="mono">{v}</td></tr>)}</tbody></table>;
}

export default function AiModels() {
  const { user } = useAuth();
  const { crew, selected, select, current } = useSelectedAstronaut();
  const models = useApi<any>("/ai/models");
  const assess = useApi<any>(selected ? `/ai/astronauts/${selected}/assessments` : null);
  const guidance = useApi<any>(selected ? `/ai/astronauts/${selected}/exercise-guidance` : null);
  const [busy, setBusy] = useState<string | null>(null);
  const [importNote, setImportNote] = useState<string | null>(null);
  const can = isCrewWide(user);

  const toggle = async (id: string, enabled: boolean) => {
    setBusy(id);
    try { await api(`/ai/models/${id}`, { method: "PUT", body: { enabled } }); models.reload(); } finally { setBusy(null); }
  };
  const refresh = async () => {
    if (!selected) return;
    setBusy("run");
    try { await api(`/ai/astronauts/${selected}/run`, { method: "POST" }); assess.reload(); guidance.reload(); } finally { setBusy(null); }
  };
  const importFile = async (file: File) => {
    setImportNote(null);
    let body: unknown;
    try { body = JSON.parse(await file.text()); }
    catch { setImportNote("That file is not a JSON model set."); return; }
    setBusy("import");
    try {
      const saved = await api<any>("/ai/models/import", { body });
      setImportNote(`${saved.name} is in. Run the models and its alerts show up with the others.`);
      models.reload();
    } catch (e: any) { setImportNote(e.message); }
    finally { setBusy(null); }
  };
  const removeImported = async (id: string) => {
    setBusy(id);
    try { await api(`/ai/models/${id}`, { method: "DELETE" }); models.reload(); }
    finally { setBusy(null); }
  };

  const byId: Record<string, any> = Object.fromEntries((models.data?.models ?? []).map((m: any) => [m.id, m]));
  return (
    <>
      <div className="page-head">
        <div><h1>AI models</h1>
          <p>Every model is a plug-in with a manifest: what it needs, what data it learned from, how it was evaluated, and whether it is validated on astronauts (none are yet).</p></div>
        <div className="spacer" />
        <AstronautPicker crew={crew} selected={selected} onSelect={select} />
      </div>

      <Card title={`Latest assessments${current ? ` · ${current.callsign}` : ""}`}
        extra={<button className="btn" disabled={busy === "run"} onClick={refresh}>{busy === "run" ? "Running…" : "Run models now"}</button>}>
        {!assess.data ? <Loading /> : (
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Model</th><th>Status</th><th>Result</th><th>Explanation</th><th>Evidence</th></tr></thead>
              <tbody>{assess.data.assessments.map((a: any) => (
                <tr key={a.model_id}>
                  <td>{byId[a.model_id]?.name ?? a.model_id}<div className="small faint mono">{a.model_id}@{a.model_version}</div></td>
                  <td>{a.status === "ok" ? <Badge kind={SEV[a.severity]}>{a.severity === "none" ? "no concern" : a.severity}</Badge> : <Badge kind="neutral">{a.status.replace("_", " ")}</Badge>}</td>
                  <td className="mono small">{a.score_label || (a.score != null ? fmt(a.score, 2) : "—")}</td>
                  <td className="small">{a.explanation}{a.recommendation && <div className="muted">↳ {a.recommendation}</div>}</td>
                  <td><Badge kind={EVIDENCE[a.evidence_level]?.kind ?? "neutral"}>{EVIDENCE[a.evidence_level]?.label ?? a.evidence_level}</Badge></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {guidance.data && (
          <div className="small" style={{ marginTop: 10 }}>
            <b>Exercise guidance (contract exercise_guidance.v1):</b> <Badge kind={guidance.data.readiness === "proceed" ? "ok" : guidance.data.readiness === "insufficient_data" ? "neutral" : "caution"}>{guidance.data.readiness.replace(/_/g, " ")}</Badge>{" "}
            {guidance.data.recommendation} <span className="faint">{guidance.data.rationale.join(" ")}</span>
          </div>
        )}
      </Card>

      <Card title="Import a model">
        <div className="col" style={{ gap: 10 }}>
          <div className="small">Download the fatigue build-up set, or bring your own file in that same shape. Change the metric or the lines, then import it. The model runs with the others. When a reading crosses the line, an alert is filed on that astronaut, next to the alerts already there.</div>
          <div className="row">
            <a className="btn" href="/models/fatigue-buildup.health01.json" download="fatigue-buildup.health01.json">Download the set</a>
            {can && (
              <label className="btn primary" style={{ cursor: "pointer" }}>
                {busy === "import" ? "Importing…" : "Import a model file"}
                <input type="file" accept=".json,application/json" hidden disabled={busy === "import"} onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void importFile(f); }} />
              </label>
            )}
          </div>
          {!can && <div className="small muted">Sign in as mission control to import a set.</div>}
          {importNote && <div className="small">{importNote}</div>}
        </div>
      </Card>

      {!models.data ? <Loading /> : (
        <div className="grid g2">
          {models.data.models.map((m: any) => {
            const ev = EVIDENCE[m.evidence_level] ?? { label: m.evidence_level, kind: "neutral" };
            return (
              <Card key={m.id} title={<div><h2>{m.name}</h2><div className="small faint mono">{m.id} · v{m.version} · {m.category}</div></div>}
                extra={<>
                  <Badge kind={ev.kind}>{ev.label}</Badge>
                  {m.status !== "ready" && <Badge kind="caution">{m.status.replace("_", " ")}</Badge>}
                  {m.imported && <Badge kind="info">imported</Badge>}
                  <Badge kind={m.enabled ? "ok" : "neutral"}>{m.enabled ? "enabled" : "disabled"}</Badge>
                  {can && <button className="btn ghost" style={{ padding: "3px 10px" }} disabled={busy === m.id} onClick={() => toggle(m.id, !m.enabled)}>{m.enabled ? "Disable" : "Enable"}</button>}
                  {can && m.imported && <button className="btn ghost" style={{ padding: "3px 10px" }} disabled={busy === m.id} onClick={() => removeImported(m.id)}>Remove</button>}
                </>}>
                <div className="col" style={{ gap: 8 }}>
                  <div className="small">{m.description}</div>
                  {m.imported && m.rules && (
                    <div className="small muted">Watches {m.rules.metric}. {m.alerting?.emit_alerts ? "Alerts are on." : "Alerts are off."} {m.rules.mode === "value" ? `Line at ${m.rules.caution_value}.` : `Caution when z reaches ${m.rules.caution_z}.`}</div>
                  )}
                  <div className="small muted"><b>Use:</b> {m.intended_use} <b>Not for:</b> {m.not_intended_for}</div>
                  <div className="evidence">{m.inputs.map((i: any) => <span key={i.metric}>{i.metric} [{i.unit}]{i.required ? "" : " (optional)"}</span>)}</div>
                  <Metrics m={m} />
                  <div className="small faint">
                    {m.datasets.map((d: any) => <div key={d.name}>Data: <a href={d.source} target="_blank" rel="noreferrer">{d.name}</a> · {d.license} · {d.population}</div>)}
                    Validated on astronauts: <b>{m.validated_on_astronauts ? "yes" : "no"}</b> · runs on: {m.execution.environments.join(", ")} · timeout {m.execution.timeout_s}s
                    {m.health?.last_error && <div className="err">Last error: {m.health.last_error}</div>}
                    {m.load_error && <div className="err">Load error: {m.load_error}</div>}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </>
  );
}
