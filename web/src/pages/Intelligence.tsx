import { Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { METRIC_LABEL, type Alert, type Contributor, type Predictions } from "../api";
import { AstronautPicker, useSelectedAstronaut } from "../components/AstronautPicker";
import { AlertItem, Badge, Card, chartTooltip, fmt, Loading } from "../components/ui";
import { useApi, useLive } from "../hooks";

function ModelCard({ m }: { m: any }) {
  const met = m.metrics || {};
  let rows: [string, string][] = [];
  if (m.id.startsWith("anomaly") && met.model) rows = [["ROC-AUC", fmt(met.model.roc_auc, 3)], ["Precision", fmt(met.model.precision, 2)], ["Recall", fmt(met.model.recall, 2)], ["False-positive rate", fmt(met.model.false_positive_rate, 3)], ["Rule baseline AUC (|z RHR|)", fmt(met["baseline_rule_abs_z_rhr_gt_2.5"]?.roc_auc, 3)]];
  if (m.id.startsWith("fatigue") && met.model) rows = [["MAE (1–7 scale)", fmt(met.model.mae, 2)], ["R²", fmt(met.model.r2, 2)], ["Persistence baseline MAE", fmt(met.baseline_persistence_yesterday?.mae, 2)], ["Mean baseline MAE", fmt(met.baseline_mean?.mae, 2)]];
  if (m.id.startsWith("forecast") && met.metrics) rows = Object.entries(met.metrics).map(([k, v]: any) => [`${METRIC_LABEL[k] ?? k} 7-day MAE`, `${fmt(v.backtest.mae_model, 2)} (naive ${fmt(v.backtest.mae_naive_last_value, 2)})`]);
  return (
    <Card title={<div><h2>{m.name}</h2><div className="small faint mono">{m.id}</div></div>} extra={<Badge kind={m.available ? "ok" : "warning"}>{m.available ? "loaded" : "missing"}</Badge>}>
      <div className="small muted">{m.type} · inputs: {m.inputs.map((i: string) => METRIC_LABEL[i] ?? i).join(", ")}</div>
      <div className="divider" />
      <h3>Evaluation <Badge kind="sim">SIMULATED DATA</Badge></h3>
      <table className="tbl" style={{ marginTop: 6 }}><tbody>{rows.map(([k, v]) => <tr key={k}><td className="muted">{k}</td><td className="mono">{v}</td></tr>)}</tbody></table>
      <div className="small faint" style={{ marginTop: 6 }}>{met.evaluation_data}</div>
      <div className="divider" />
      <h3>Limitations</h3>
      <ul className="small muted" style={{ margin: "6px 0 0", paddingLeft: 18 }}>{m.limitations.map((l: string) => <li key={l}>{l}</li>)}</ul>
    </Card>
  );
}

export default function Intelligence() {
  const { crew, selected, select, current } = useSelectedAstronaut();
  const pred = useApi<Predictions>(selected ? `/astronauts/${selected}/predictions` : null);
  const alerts = useApi<{ alerts: Alert[] }>(selected ? `/astronauts/${selected}/alerts?include_environment=false&limit=12` : null);
  const models = useApi<{ models: any[] }>("/models");
  useLive((e) => {
    if (e.type === "alert" && e.alert.astronaut_id === selected) alerts.reload();
    if (e.type === "measurements" && e.items.some((i) => i.astronaut_id === selected && i.metric === "resting_heart_rate")) pred.reload();
  });
  const p = pred.data;
  const latest = p?.anomaly?.latest;
  const threshold = latest?.threshold;
  const hist = (p?.anomaly?.history ?? []).map((h) => ({ ...h, d: h.date.slice(5) }));

  return (
    <>
      <div className="page-head">
        <div><h1>Health insights{current ? ` · ${current.callsign}` : ""}</h1><p>The original three models (anomaly, fatigue, forecast) run on the server with no outside AI service. The real-data models are under AI › Models.</p></div>
        <div className="spacer" />
        <AstronautPicker crew={crew} selected={selected} onSelect={select} />
      </div>
      {p && <div className="banner">{p.disclaimer}</div>}
      {!p ? <Loading /> : (
        <div className="grid g3">
          <Card title="Model 1 · Personalised anomaly detection" className="span2" extra={latest?.status === "scored" ? <Badge kind={latest.is_anomaly ? "caution" : "ok"}>{latest.is_anomaly ? "UNUSUAL TODAY" : "within normal variation"}</Badge> : <Badge kind="neutral">{latest?.status ?? "n/a"}</Badge>}>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={hist} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
                <CartesianGrid vertical={false} />
                <XAxis dataKey="d" minTickGap={12} />
                <YAxis domain={[0, "auto"]} />
                <Tooltip {...chartTooltip} formatter={(v: any, _n, it: any) => [`${fmt(v, 3)} (percentile ${fmt((it.payload.percentile ?? 0) * 100, 0)})`, "anomaly score"]} />
                {threshold && <ReferenceLine y={threshold} stroke="#b86e00" strokeDasharray="4 4" label={{ value: "threshold", fill: "#b86e00", fontSize: 10, position: "insideTopLeft" }} />}
                <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                  {hist.map((h, i) => <Cell key={i} fill={h.is_anomaly ? "#b86e00" : "#1d2bdb"} fillOpacity={h.is_anomaly ? 0.95 : 0.55} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            {latest?.status === "scored" && (
              <>
                <div className="small muted" style={{ margin: "8px 0" }}>
                  Latest day {latest.date}: score {fmt(latest.score, 3)} (higher than {fmt(latest.score_percentile * 100, 0)}% of nominal training days) · reliability {latest.reliability}
                  {latest.missing?.length > 0 && <> · missing inputs: {latest.missing.join(", ")}</>}
                </div>
                <table className="tbl">
                  <thead><tr><th>Measurement</th><th>Today</th><th>Personal baseline</th><th>Usual range</th><th>Deviation (robust z)</th></tr></thead>
                  <tbody>{latest.contributors.map((c: Contributor) => (
                    <tr key={c.metric}>
                      <td>{c.label}</td><td className="mono">{fmt(c.value)}</td><td className="mono">{fmt(c.baseline_median)} <span className="faint">({c.baseline_days} d)</span></td>
                      <td className="mono">{c.baseline_range.map((x) => fmt(x)).join(" – ")}</td>
                      <td className="mono" style={{ color: Math.abs(c.z) >= 2.5 ? "var(--caution)" : undefined }}>{c.z > 0 ? "+" : ""}{fmt(c.z, 2)} {c.direction}</td>
                    </tr>))}</tbody>
                </table>
              </>
            )}
          </Card>

          <Card title="Model 2 · Fatigue estimate" extra={<Badge kind="sim">SIMULATION MODEL</Badge>}>
            {p.fatigue.status === "estimated" ? (
              <div className="col">
                <div className="big">{fmt(p.fatigue.fatigue_estimate, 1)}<span className="unit">/ 7</span></div>
                <div className="muted">{p.fatigue.category} · 80% range {p.fatigue.interval_80?.map((x) => fmt(x, 1)).join("–")}</div>
                <div style={{ position: "relative", height: 10, borderRadius: 99, background: "linear-gradient(90deg,#2e7d32,#b86e00,#d81b1b)" }}>
                  <div style={{ position: "absolute", left: `${((p.fatigue.interval_80![0] - 1) / 6) * 100}%`, width: `${((p.fatigue.interval_80![1] - p.fatigue.interval_80![0]) / 6) * 100}%`, top: -3, height: 16, border: "2px solid #17191f", borderRadius: 6 }} />
                </div>
                <div className="small faint">{p.fatigue.scale}</div>
                <table className="tbl"><tbody>{Object.entries(p.fatigue.inputs ?? {}).map(([k, v]) => <tr key={k}><td className="muted">{k.replace(/_/g, " ")}</td><td className="mono">{v ?? <span className="faint">missing</span>}</td></tr>)}</tbody></table>
              </div>
            ) : <div className="empty">{p.fatigue.status}</div>}
          </Card>

          {p.forecasts.series.map((s) => (
            <Card key={s.metric} title={`Model 3 · ${METRIC_LABEL[s.metric] ?? s.metric} 7-day forecast`} extra={s.status === "forecast" ? <Badge kind={s.trend_direction === "stable" ? "neutral" : "info"}>{s.trend_direction}</Badge> : null}>
              {s.status !== "forecast" ? <div className="empty">Insufficient data ({s.required} days required)</div> : (
                <>
                  <ResponsiveContainer width="100%" height={170}>
                    <ComposedChart data={s.points!.map((pt) => ({ ...pt, band: [pt.lower_80, pt.upper_80], d: pt.date.slice(5) }))} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
                      <CartesianGrid vertical={false} />
                      <XAxis dataKey="d" />
                      <YAxis domain={["auto", "auto"]} />
                      <Tooltip {...chartTooltip} />
                      <Area dataKey="band" name="80% interval" stroke="none" fill="#1d2bdb" fillOpacity={0.18} />
                      <Line dataKey="value" name="forecast" stroke="#1d2bdb" strokeWidth={2} strokeDasharray="5 3" dot={{ r: 2 }} />
                      <ReferenceLine y={s.recent_mean_7d} stroke="#858d9c" strokeDasharray="2 4" />
                    </ComposedChart>
                  </ResponsiveContainer>
                  <div className="small muted">Recent 7-day mean {fmt(s.recent_mean_7d, 1)} → day-7 estimate {fmt(s.points!.at(-1)!.value, 1)} (projected change {s.projected_change! > 0 ? "+" : ""}{fmt(s.projected_change, 2)}).
                    {s.backtest && <> Backtest MAE {fmt(s.backtest.mae_model, 2)} vs naive {fmt(s.backtest.mae_naive_last_value, 2)} (simulated).</>}</div>
                </>
              )}
            </Card>
          ))}

          <Card title="Risk explanations (recent alerts)" className="span2">
            <div className="col">
              {(alerts.data?.alerts ?? []).length === 0 && <div className="empty">No open alerts for this astronaut</div>}
              {(alerts.data?.alerts ?? []).slice(0, 6).map((a) => <AlertItem key={a.id} a={a} />)}
            </div>
          </Card>
          <Card title="How alerts are generated">
            <ul className="small muted" style={{ paddingLeft: 18, margin: 0 }}>
              <li><b>Threshold rules</b> compare today with your own robust baseline (median ± scaled MAD over 21 days, excluding the last 2 days so an ongoing change cannot hide itself).</li>
              <li><b>The anomaly model</b> flags unusual <i>combinations</i> of deviations that single rules can miss.</li>
              <li><b>Each alert lists the exact measurements</b> and baseline values that triggered it.</li>
              <li>Measurements and model estimates are always labelled separately.</li>
            </ul>
          </Card>
        </div>
      )}
      <h2 style={{ marginTop: 8 }}>Model cards</h2>
      <div className="grid g3">{(models.data?.models ?? []).map((m) => <ModelCard key={m.id} m={m} />)}</div>
    </>
  );
}
