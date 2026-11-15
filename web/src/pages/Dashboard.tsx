import { useMemo } from "react";
import { Area, Bar, CartesianGrid, ComposedChart, Legend, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { Summary } from "../api";
import { AstronautPicker, useSelectedAstronaut } from "../components/AstronautPicker";
import { Card, chartTooltip, DataClassBadge, Loading, MetricTile } from "../components/ui";
import { useApi, useLive } from "../hooks";

const short = (d: string) => d.slice(5);

function BaselineChart({ data, metric, summary, color, unit, bars }: { data: any[]; metric: string; summary?: any; color: string; unit: string; bars?: boolean }) {
  const range = summary?.baseline_range;
  return (
    <ResponsiveContainer width="100%" height={210}>
      <ComposedChart data={data} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="date" tickFormatter={short} minTickGap={18} />
        <YAxis domain={["auto", "auto"]} />
        <Tooltip {...chartTooltip} formatter={(v: any) => [`${v} ${unit}`, ""]} />
        {range && <ReferenceArea y1={range[0]} y2={range[1]} fill={color} fillOpacity={0.08} stroke="none" />}
        {summary?.baseline_median != null && <ReferenceLine y={summary.baseline_median} stroke={color} strokeDasharray="4 4" strokeOpacity={0.6} />}
        {bars ? <Bar dataKey={metric} fill={color} fillOpacity={0.75} radius={[4, 4, 0, 0]} />
          : <Line dataKey={metric} stroke={color} strokeWidth={2} dot={{ r: 2 }} connectNulls />}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export default function Dashboard() {
  const { crew, selected, select, current } = useSelectedAstronaut();
  const summary = useApi<Summary>(selected ? `/astronauts/${selected}/summary` : null);
  const daily = useApi<any>(selected ? `/astronauts/${selected}/measurements?resolution=daily&days=45` : null);
  const hr = useApi<any>(selected ? `/astronauts/${selected}/measurements?metric=heart_rate&days=5` : null);
  useLive((e) => {
    if (e.type === "measurements" && e.items.some((i) => i.astronaut_id === selected && i.metric !== "heart_rate")) { summary.reload(); daily.reload(); }
    if (e.type === "measurements" && e.items.some((i) => i.astronaut_id === selected && i.metric === "heart_rate")) hr.reload();
  });

  const byMetric = useMemo(() => {
    const out: Record<string, any> = {};
    Object.values(summary.data?.domains ?? {}).forEach((d) => d.metrics.forEach((m) => (out[m.metric] = m)));
    return out;
  }, [summary.data]);
  const hrData = (hr.data?.items ?? []).map((i: any) => ({ t: i.timestamp.slice(5, 16).replace("T", " "), hr: i.value }));
  const d = daily.data?.items ?? [];
  const s = summary.data;

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{current ? `${current.callsign} · ${current.role}` : "Astronaut dashboard"}</h1>
          <p>Shaded band = this astronaut's usual range (10th to 90th percentile of their own recent days).</p>
        </div>
        <div className="spacer" />
        <AstronautPicker crew={crew} selected={selected} onSelect={select} />
        <DataClassBadge value={current?.data_class} />
      </div>
      {!s ? <Loading /> : (
        <>
          <div className="grid g4">
            {["resting_heart_rate", "hrv_sdnn", "blood_pressure_systolic", "body_temperature", "blood_glucose", "body_mass", "sleep_duration", "steps", "exercise_minutes", "fatigue_score", "mood_score", "stress_score"]
              .filter((k) => byMetric[k]).map((k) => <MetricTile key={k} m={byMetric[k]} />)}
          </div>
          {s.unavailable_metrics.length > 0 && <div className="small faint">Not available for this astronaut: {s.unavailable_metrics.join(", ")}</div>}
          <div className="grid g2">
            <Card title="Heart rate (hourly, last 5 days)" extra={<span className="small faint">{hrData.length} samples</span>}>
              <ResponsiveContainer width="100%" height={210}>
                <LineChart data={hrData} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="t" minTickGap={40} />
                  <YAxis domain={["auto", "auto"]} />
                  <Tooltip {...chartTooltip} />
                  <Line dataKey="hr" name="HR (bpm)" stroke="#d81b1b" dot={false} strokeWidth={1.6} isAnimationActive={false} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Resting heart rate vs baseline" extra={<span className="small faint">bpm, daily</span>}>
              <BaselineChart data={d} metric="resting_heart_rate" summary={byMetric.resting_heart_rate} color="#d81b1b" unit="bpm" />
            </Card>
            <Card title="Heart-rate variability (SDNN) vs baseline" extra={<span className="small faint">ms, daily</span>}>
              <BaselineChart data={d} metric="hrv_sdnn" summary={byMetric.hrv_sdnn} color="#005c96" unit="ms" />
            </Card>
            <Card title="Sleep duration" extra={<span className="small faint">h · dashed = personal median · 7.5 h reference</span>}>
              <ResponsiveContainer width="100%" height={210}>
                <ComposedChart data={d} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="date" tickFormatter={short} minTickGap={18} />
                  <YAxis domain={[0, 10]} />
                  <Tooltip {...chartTooltip} />
                  <ReferenceLine y={7.5} stroke="#858d9c" strokeDasharray="2 4" />
                  {byMetric.sleep_duration?.baseline_median && <ReferenceLine y={byMetric.sleep_duration.baseline_median} stroke="#1d2bdb" strokeDasharray="4 4" />}
                  <Bar dataKey="sleep_duration" name="Sleep (h)" fill="#1d2bdb" fillOpacity={0.8} radius={[4, 4, 0, 0]} />
                </ComposedChart>
              </ResponsiveContainer>
              {s.domains.sleep?.sleep_timing_variability_h != null && (
                <div className="small muted">Sleep timing variability (7 nights): ±{s.domains.sleep.sleep_timing_variability_h} h
                  {s.domains.sleep.circadian_disruption && <span style={{ color: "var(--caution)" }}> · circadian disruption indicator</span>}
                  {" · "}7-night sleep debt vs 7.5 h: {s.domains.sleep.sleep_debt_7d_h_vs_7_5h} h</div>
              )}
            </Card>
            <Card title="Activity & training adherence" extra={<span className="small faint">steps (bars) · exercise min (line)</span>}>
              <ResponsiveContainer width="100%" height={210}>
                <ComposedChart data={d} margin={{ top: 6, right: 0, left: -12, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="date" tickFormatter={short} minTickGap={18} />
                  <YAxis yAxisId="s" />
                  <YAxis yAxisId="e" orientation="right" />
                  <Tooltip {...chartTooltip} />
                  <Bar yAxisId="s" dataKey="steps" name="Steps" fill="#6c9cff" fillOpacity={0.55} radius={[3, 3, 0, 0]} />
                  <Line yAxisId="e" dataKey="exercise_minutes" name="Exercise (min)" stroke="#b86e00" strokeWidth={2} dot={false} />
                  <ReferenceLine yAxisId="e" y={90} stroke="#b86e00" strokeDasharray="3 4" strokeOpacity={0.5} />
                </ComposedChart>
              </ResponsiveContainer>
              {s.domains.activity?.training_adherence_7d_pct != null && <div className="small muted">Training adherence (days ≥ {s.domains.activity.exercise_target_min} min, last 7): {s.domains.activity.training_adherence_7d_pct}%</div>}
            </Card>
            <Card title="Wellbeing check-ins" extra={<span className="small faint">fatigue 1–7 · stress 1–10 · mood 1–5</span>}>
              <ResponsiveContainer width="100%" height={210}>
                <ComposedChart data={d} margin={{ top: 6, right: 8, left: -12, bottom: 0 }}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="date" tickFormatter={short} minTickGap={18} />
                  <YAxis domain={[0, 10]} />
                  <Tooltip {...chartTooltip} />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  <Area dataKey="fatigue_score" name="Fatigue" stroke="#d81b1b" fill="#d81b1b" fillOpacity={0.12} />
                  <Line dataKey="stress_score" name="Stress" stroke="#b86e00" dot={false} />
                  <Line dataKey="mood_score" name="Mood" stroke="#2e7d32" dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </Card>
          </div>
          <Card title="Baseline comparison (all metrics)">
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th>Domain</th><th>Metric</th><th>Latest</th><th>7-day avg</th><th>Personal baseline</th><th>Usual range</th><th>Δ vs baseline</th><th>Status</th></tr></thead>
                <tbody>
                  {Object.entries(s.domains).flatMap(([dom, dd]) => dd.metrics.filter((m) => m.status !== "no_data").map((m) => (
                    <tr key={m.metric}>
                      <td className="muted">{dom}</td><td>{m.label}</td>
                      <td className="mono">{m.latest} {m.unit}</td><td className="mono">{m.avg_7d}</td>
                      <td className="mono">{m.baseline_median} <span className="faint">({m.baseline_days} d)</span></td>
                      <td className="mono">{m.baseline_range?.join(" – ")}</td>
                      <td className="mono">{m.delta_vs_baseline_pct != null ? `${m.delta_vs_baseline_pct > 0 ? "+" : ""}${m.delta_vs_baseline_pct}%` : "—"}</td>
                      <td style={{ color: m.concern ? "var(--caution)" : "var(--muted)" }}>{m.status.replace(/_/g, " ")}</td>
                    </tr>
                  )))}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </>
  );
}
