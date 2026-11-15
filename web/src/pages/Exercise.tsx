import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { AstronautPicker, useSelectedAstronaut } from "../components/AstronautPicker";
import { Badge, Card, Loading, chartTooltip } from "../components/ui";
import { useApi } from "../hooks";
import CameraPanel from "../exercise/CameraPanel";
import ExerciseDemo from "../exercise/ExerciseDemo";
import WorkoutPlayer from "../exercise/WorkoutPlayer";

type Goal = { period: string; metric: string; label: string; target: number; actual: number; pct: number; example_only?: boolean };
type Progress = {
  streak_days: number; missed_dates: string[]; goals: Goal[];
  adherence_weeks: { week_start: string; sessions: number; pct: number }[];
  series: { date: string; minutes: number; sessions: number }[];
  wearable_exercise_minutes_7d: number | null;
  totals: { sessions: number; minutes: number }; disclaimer: string;
};
type Program = {
  id: string; name: string; kind: string; summary: string; disclaimer: string; progression: string;
  schedule: { weekdays: number[]; sessions_per_week: number };
  blocks: { weekday: number; focus: string; items: { exercise_id: string; name: string; sets: number; reps: number | null; duration_s: number | null; rest_s: number; intensity: string }[] }[];
  requires_human_review?: boolean; review_reasons?: string[];
};
type Exercise = { id: string; name: string; category: string; description: string; equipment: string[]; tracking: string | null; cues: string[]; steps?: string[]; default_sets: number; default_reps: number | null; default_duration_s: number | null; intensity: string };
type Rec = { reason: string; source: string; model: string | null; confidence: number | null; requires_human_review: boolean; review_reasons: string[]; items: { exercise_id: string; name: string; sets: number; reps: number | null; duration_s: number | null; intensity: string; reason: string }[]; disclaimer: string; fallback: string | null };
type Profile = { fitness_level: string; focus: string; limitations: string; equipment: string[]; mission_phase: string; notes: string };

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const TABS = ["Today", "Camera coach", "Program", "History", "Library", "Goals"] as const;
type Guidance = { readiness: "proceed" | "reduce_intensity" | "rest_and_recheck" | "insufficient_data"; recommendation: string; rationale: string[]; not_medical_advice?: boolean };
const READY: Record<Guidance["readiness"], [string, string, string]> = {
  proceed: ["Go for training", "ok", "Signals look like your usual pattern."],
  reduce_intensity: ["Train lighter today", "caution", "Something is off from your baseline."],
  rest_and_recheck: ["Rest and re-check", "warning", "A warning is open. Talk to the flight surgeon first."],
  insufficient_data: ["Not enough data", "neutral", "Do a fatigue check-in so the system can judge."],
};

function Ring({ pct, label, sub }: { pct: number; label: string; sub: string }) {
  const r = 38, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, pct));
  return (
    <div className="ring">
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle cx="50" cy="50" r={r} className="ring-bg" />
        <circle cx="50" cy="50" r={r} className="ring-fg" strokeDasharray={`${(v / 100) * c} ${c}`} transform="rotate(-90 50 50)" />
      </svg>
      <div className="ring-text"><b>{Math.round(pct)}%</b><span>{label}</span></div>
      <small>{sub}</small>
    </div>
  );
}

export default function ExercisePage() {
  const { crew, selected, select, current } = useSelectedAstronaut();
  const [tab, setTab] = useState<(typeof TABS)[number]>("Today");
  const [guided, setGuided] = useState(false);
  const id = selected;
  const progress = useApi<Progress>(id ? `/exercise/astronauts/${id}/progress` : null);
  const program = useApi<{ active: Program; general: Program; personalized: Program; mission: Program; disclaimer: string }>(id ? `/exercise/astronauts/${id}/program` : null);
  const catalog = useApi<{ exercises: Exercise[]; disclaimer: string }>("/exercise/catalog");
  const sessions = useApi<{ sessions: { id: number; source: string; started_at: string; summary: { minutes?: number; reps?: number }; notes: string; exercises: { exercise_id: string }[]; data_class: string; perceived_exertion: number | null; heart_rate_avg: number | null }[] }>(id ? `/exercise/astronauts/${id}/sessions` : null);
  const recs = useApi<Rec>(id ? `/exercise/astronauts/${id}/recommendations` : null);
  const profile = useApi<Profile>(id ? `/exercise/astronauts/${id}/profile` : null);
  const guidance = useApi<Guidance>(id ? `/ai/astronauts/${id}/exercise-guidance` : null);
  const alerts = useApi<{ alerts: { id: number; category: string; severity: string; title: string; message: string; recommendation: string; acknowledged: boolean }[] }>(id ? `/astronauts/${id}/alerts?include_acknowledged=true` : null);
  const now = new Date();
  const [month, setMonth] = useState({ year: now.getFullYear(), month: now.getMonth() + 1 });
  const calendar = useApi<{ days: { date: string; minutes: number; sessions: number; scheduled: boolean; missed: boolean }[] }>(
    id && tab === "History" ? `/exercise/astronauts/${id}/calendar?year=${month.year}&month=${month.month}` : null);

  function reloadAll() {
    progress.reload(); sessions.reload(); recs.reload(); alerts.reload(); calendar.reload(); guidance.reload();
  }

  const exerciseAlerts = (alerts.data?.alerts ?? []).filter((a) => a.category === "exercise" && !a.acknowledged);
  const todayIdx = (now.getDay() + 6) % 7;
  const todayBlock = program.data?.active?.blocks.find((b) => b.weekday === todayIdx);
  const workoutBlock = todayBlock ?? program.data?.active?.blocks[0];   // rest day: offer the program's first session
  const day = progress.data?.goals.find((g) => g.period === "day");
  const week = progress.data?.goals.find((g) => g.period === "week");
  const monthGoal = progress.data?.goals.find((g) => g.period === "month");
  const ready = guidance.data ? READY[guidance.data.readiness] : null;
  const achievements = useMemo(() => {
    const g = progress.data;
    if (!g) return [];
    const items: string[] = [];
    if (g.streak_days >= 3) items.push(`${g.streak_days}-day streak`);
    if (week && week.pct >= 100) items.push("Week target met");
    if (monthGoal && monthGoal.pct >= 100) items.push("Month target met");
    return items;
  }, [progress.data, week, monthGoal]);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Exercise & Fitness</h1>
          <p>Training for {current?.callsign ?? "the crew"}: today's plan, a camera rep coach, and progress against example targets.</p>
        </div>
        <div className="spacer" />
        <AstronautPicker crew={crew} selected={selected} onSelect={select} />
      </div>
      <div className="tabs ex-tabs" role="tablist">
        {TABS.map((name) => <button type="button" key={name} role="tab" aria-selected={tab === name} className={tab === name ? "on" : ""} onClick={() => setTab(name)}>{name}</button>)}
      </div>
      {!id && <Loading what="Exercise" />}

      {tab === "Today" && guided && id && workoutBlock && (
        <WorkoutPlayer items={workoutBlock.items} catalog={catalog.data?.exercises ?? []} astronautId={id}
          onClose={() => setGuided(false)} onSaved={reloadAll} />
      )}
      {tab === "Today" && guided && id && !workoutBlock && (
        program.data ? <div className="empty">This program has no session to start. <button type="button" className="btn" onClick={() => setGuided(false)}>Back to today</button></div> : <Loading what="the workout" />
      )}
      {tab === "Today" && !guided && id && !progress.data && (progress.error ? <div className="err">{progress.error}</div> : <Loading what="Today" />)}
      {tab === "Today" && progress.data && !guided && (
        <>
          <section className={`ex-hero ${ready?.[1] ?? "neutral"}`}>
            <div className="ex-ready">
              <span className="ex-kicker">Readiness check</span>
              <h2>{ready?.[0] ?? "Checking…"}</h2>
              <p>{guidance.data?.recommendation ?? ready?.[2]}</p>
              {guidance.data?.rationale?.length ? <ul className="small muted">{guidance.data.rationale.slice(0, 3).map((r) => <li key={r}>{r}</li>)}</ul> : null}
              <div className="row" style={{ marginTop: 12 }}>
                <button className="btn primary big-btn" disabled={!workoutBlock} onClick={() => setGuided(true)}>▶ {todayBlock ? "Start today's workout" : "Start a workout"}</button>
                <button className="btn big-btn" onClick={() => setTab("Camera coach")}>Camera coach</button>
                <button className="btn big-btn" onClick={() => setTab("History")}>Log a workout</button>
              </div>
              <p className="small faint" style={{ marginTop: 10 }}>From the AI engine's exercise_guidance.v1 contract. Not medical advice.</p>
            </div>
            <div className="ex-rings">
              <Ring pct={day?.pct ?? 0} label="today" sub={day ? `${day.actual}/${day.target} ${day.metric}` : "no target"} />
              <Ring pct={week?.pct ?? 0} label="this week" sub={week ? `${week.actual}/${week.target} ${week.metric}` : "no target"} />
              <div className="ex-streak"><b>{progress.data.streak_days}</b><span>day streak</span>
                <div className="row" style={{ justifyContent: "center", marginTop: 6 }}>{achievements.map((a) => <Badge key={a} kind="ok">{a}</Badge>)}</div>
              </div>
            </div>
          </section>

          {exerciseAlerts.map((a) => (
            <div key={a.id} className={`alert-item ${a.severity}`}>
              <div className="row"><Badge kind={a.severity}>{a.severity}</Badge><b>{a.title}</b></div>
              <div className="small">{a.message}</div>
              {a.recommendation && <div className="small muted">↳ {a.recommendation}</div>}
            </div>
          ))}

          <div className="grid g2">
            <Card title={`Today's plan · ${DAYS[todayIdx]}`} extra={<Badge kind="sim">example program</Badge>}>
              {!todayBlock && <div className="empty">Rest day in the {program.data?.active?.name ?? "program"}. Light mobility is fine.</div>}
              {todayBlock && (
                <>
                  <p className="small muted">{todayBlock.focus}</p>
                  <ol className="ex-plan">
                    {todayBlock.items.map((it) => {
                      const ex = catalog.data?.exercises.find((e) => e.id === it.exercise_id);
                      return (
                        <li key={it.exercise_id}>
                          <div className="row"><b>{it.name}</b>{ex?.tracking && <Badge kind="info">camera</Badge>}</div>
                          <span className="ex-dose">{it.sets} × {it.reps ?? `${it.duration_s}s`}</span>
                          <span className="small faint">rest {it.rest_s}s · {it.intensity}</span>
                          {ex?.cues?.[0] && <span className="small muted">{ex.cues[0]}</span>}
                        </li>
                      );
                    })}
                  </ol>
                </>
              )}
            </Card>
            <Card title="Suggested for you">
              {recs.data ? (
                <>
                  {recs.data.requires_human_review && <div className="banner" style={{ marginBottom: 10 }}><b>Needs a person.</b> {recs.data.review_reasons.join(" ")}</div>}
                  <p className="small">{recs.data.reason}</p>
                  <div className="col" style={{ marginTop: 8 }}>
                    {recs.data.items.slice(0, 4).map((item) => (
                      <div key={item.exercise_id + item.reason} className="ex-sug">
                        <b>{item.name}</b><span className="ex-dose">{item.sets} × {item.reps ?? `${item.duration_s}s`}</span>
                        <span className="small muted">{item.reason}</span>
                      </div>
                    ))}
                  </div>
                  <p className="small faint" style={{ marginTop: 8 }}>Source {recs.data.source}{recs.data.fallback ? " (rules)" : ""}. {recs.data.disclaimer}</p>
                </>
              ) : <Loading what="Suggestions" />}
            </Card>
            <Card title="Minutes, last 30 days">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={progress.data.series}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="date" tickFormatter={(d) => String(d).slice(5)} minTickGap={16} />
                  <YAxis />
                  <Tooltip {...chartTooltip} />
                  <Bar dataKey="minutes" fill="var(--steel)" name="Minutes" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
            <Card title="Weekly adherence">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={progress.data.adherence_weeks}>
                  <CartesianGrid vertical={false} />
                  <XAxis dataKey="week_start" tickFormatter={(d) => String(d).slice(5)} />
                  <YAxis unit="%" />
                  <Tooltip {...chartTooltip} />
                  <Bar dataKey="pct" fill="var(--accent2)" name="% of weekly target" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <p className="small muted">{progress.data.totals.sessions} sessions, {progress.data.totals.minutes} minutes logged.
                {progress.data.wearable_exercise_minutes_7d != null && ` Wearable: ${progress.data.wearable_exercise_minutes_7d} min in 7 days.`}</p>
            </Card>
          </div>
          <p className="small faint">{program.data?.disclaimer ?? "Example programs, not flight protocols or medical prescriptions."}</p>
        </>
      )}

      {tab === "Program" && id && !program.data?.active && (program.error ? <div className="err">{program.error}</div> : <Loading what="Program" />)}
      {tab === "Program" && program.data?.active && (
        <ProgramView personalized={program.data.personalized} general={program.data.general} mission={program.data.mission} profile={profile.data} onSaved={() => { profile.reload(); program.reload(); recs.reload(); }} astronautId={id!} />
      )}

      {tab === "History" && id && (
        <>
          <ManualLog astronautId={id} exercises={catalog.data?.exercises ?? []} onSaved={reloadAll} history={sessions.data?.sessions ?? []} />
          <Card title="Workout calendar" extra={
            <span className="row">
              <button className="btn ghost" onClick={() => setMonth((m) => m.month === 1 ? { year: m.year - 1, month: 12 } : { ...m, month: m.month - 1 })}>‹ Prev</button>
              <span className="small mono">{month.year}-{String(month.month).padStart(2, "0")}</span>
              <button className="btn ghost" onClick={() => setMonth((m) => m.month === 12 ? { year: m.year + 1, month: 1 } : { ...m, month: m.month + 1 })}>Next ›</button>
            </span>
          }>
            <div className="cal">{DAYS.map((d) => <div key={d} className="dow">{d}</div>)}</div>
            <MonthGrid days={calendar.data?.days ?? []} />
            {calendar.loading && <Loading what="Calendar" />}
          </Card>
        </>
      )}

      {tab === "Library" && !catalog.data && (catalog.error ? <div className="err">{catalog.error}</div> : <Loading what="Library" />)}
      {tab === "Library" && catalog.data && catalog.data.exercises.length === 0 && <div className="empty">No exercises in the catalog.</div>}
      {tab === "Library" && !!catalog.data?.exercises.length && (
        <div className="grid g-auto">
          {catalog.data.exercises.map((ex) => (
            <div key={ex.id} className="tile ex-lib">
              <ExerciseDemo id={ex.id} size={120} />
              <div className="label"><b>{ex.name}</b><Badge kind={ex.tracking ? "info" : "neutral"}>{ex.tracking ? "camera" : ex.category}</Badge></div>
              <p className="small">{ex.description}</p>
              <p className="ex-dose">{ex.default_sets} × {ex.default_reps ?? `${ex.default_duration_s}s`}</p>
              <p className="small faint">{ex.intensity} · {ex.equipment.join(", ") || "no equipment"}</p>
              <ol className="small muted">{(ex.steps?.length ? ex.steps : ex.cues).map((c) => <li key={c}>{c}</li>)}</ol>
            </div>
          ))}
        </div>
      )}

      {tab === "Camera coach" && id && (
        <Card title="Camera coach" extra={<span className="small muted">Video stays on this device; only counts are saved.</span>}>
          <CameraPanel astronautId={id} onSaved={reloadAll} />
        </Card>
      )}

      {tab === "Goals" && id && !progress.data && (progress.error ? <div className="err">{progress.error}</div> : <Loading what="Goals" />)}
      {tab === "Goals" && progress.data && id && (
        <GoalsPanel key={id} astronautId={id} goals={progress.data.goals} missed={progress.data.missed_dates} onSaved={() => progress.reload()} />
      )}
    </>
  );
}

function ProgramView({ personalized, general, mission, profile, astronautId, onSaved }: { personalized: Program; general: Program; mission: Program; profile: Profile | null; astronautId: string; onSaved: () => void }) {
  const [which, setWhich] = useState<"personalized" | "general" | "mission">("personalized");
  const program = which === "general" ? general : which === "mission" ? mission : personalized;
  return (
    <div className="grid">
      <div className="tabs">
        <button type="button" className={which === "personalized" ? "on" : ""} onClick={() => setWhich("personalized")}>Personalized</button>
        <button type="button" className={which === "general" ? "on" : ""} onClick={() => setWhich("general")}>General crew</button>
        <button type="button" className={which === "mission" ? "on" : ""} onClick={() => setWhich("mission")}>Mission example</button>
      </div>
      {program?.requires_human_review && <div className="banner"><b>Review.</b> {(program.review_reasons ?? []).join(" ")}</div>}
      <Card title={program?.name ?? "Program"} extra={<Badge kind="sim">EXAMPLE</Badge>}>
        <p className="small">{program?.summary}</p>
        <p className="small muted">{program?.progression}</p>
        {(program?.blocks ?? []).map((block) => (
          <div key={block.weekday + block.focus} style={{ marginTop: 10 }}>
            <h3>{DAYS[block.weekday]} · {block.focus}</h3>
            <table className="tbl"><tbody>
              {block.items.map((item) => (
                <tr key={item.exercise_id}><td>{item.name}</td><td>{item.sets}× {item.reps ?? `${item.duration_s}s`}</td><td>rest {item.rest_s}s</td><td>{item.intensity}</td></tr>
              ))}
            </tbody></table>
          </div>
        ))}
      </Card>
      {profile && <ProfileForm key={astronautId} astronautId={astronautId} profile={profile} onSaved={onSaved} />}
    </div>
  );
}

function ProfileForm({ astronautId, profile, onSaved }: { astronautId: string; profile: Profile; onSaved: () => void }) {
  const [form, setForm] = useState(profile);
  const [msg, setMsg] = useState("");
  async function save() {
    await api(`/exercise/astronauts/${astronautId}/profile`, { method: "PUT", body: { ...form, equipment: form.equipment } });
    setMsg("Profile saved. The personalized example was rebuilt.");
    onSaved();
  }
  return (
    <Card title="Astronaut profile">
      <div className="grid g4">
        <label className="field">Level
          <select className="input" value={form.fitness_level} onChange={(e) => setForm({ ...form, fitness_level: e.target.value })}>
            {["beginner", "intermediate", "advanced"].map((v) => <option key={v}>{v}</option>)}
          </select>
        </label>
        <label className="field">Focus
          <select className="input" value={form.focus} onChange={(e) => setForm({ ...form, focus: e.target.value })}>
            {["balanced", "strength", "cardio", "mobility", "rehab"].map((v) => <option key={v}>{v}</option>)}
          </select>
        </label>
        <label className="field">Phase
          <select className="input" value={form.mission_phase} onChange={(e) => setForm({ ...form, mission_phase: e.target.value })}>
            {["preflight", "in_flight", "postflight"].map((v) => <option key={v}>{v}</option>)}
          </select>
        </label>
        <label className="field">Equipment (comma separated)
          <input className="input" value={form.equipment.join(", ")} onChange={(e) => setForm({ ...form, equipment: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) })} />
        </label>
      </div>
      <label className="field" style={{ marginTop: 10 }}>Limitation note (any text flags the plan for human review)
        <input className="input" value={form.limitations} onChange={(e) => setForm({ ...form, limitations: e.target.value })} />
      </label>
      <div className="row" style={{ marginTop: 10 }}>
        <button className="btn primary" onClick={save}>Save profile</button>
        {msg && <span className="small muted">{msg}</span>}
      </div>
    </Card>
  );
}

function MonthGrid({ days }: { days: { date: string; minutes: number; sessions: number; scheduled: boolean; missed: boolean }[] }) {
  if (!days.length) return null;
  const lead = (new Date(days[0].date + "T00:00:00").getDay() + 6) % 7;
  const cells = [...Array(lead).fill(null), ...days];
  return (
    <div className="cal" style={{ marginTop: 6 }}>
      {cells.map((d, i) => d ? (
        <div key={d.date} className={`day ${d.sessions ? "on" : ""} ${d.missed ? "miss" : ""}`}>
          <b>{Number(d.date.slice(8))}</b>
          <div className="small">{d.sessions ? `${d.minutes} min` : d.scheduled ? "planned" : ""}</div>
        </div>
      ) : <div key={`e${i}`} />)}
    </div>
  );
}

function ManualLog({ astronautId, exercises, history, onSaved }: { astronautId: string; exercises: Exercise[]; history: { id: number; source: string; started_at: string; summary: { minutes?: number; reps?: number }; notes: string; exercises: { exercise_id: string }[]; data_class: string; perceived_exertion: number | null; heart_rate_avg: number | null }[]; onSaved: () => void }) {
  const [exerciseId, setExerciseId] = useState(exercises[0]?.id ?? "squat");
  const [sets, setSets] = useState(3);
  const [reps, setReps] = useState(10);
  const [minutes, setMinutes] = useState(30);
  const [rpe, setRpe] = useState(5);
  const [hr, setHr] = useState("");
  const [notes, setNotes] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  async function submit() {
    setErr("");
    const end = new Date();
    const start = new Date(end.getTime() - minutes * 60_000);
    try {
      await api(`/exercise/astronauts/${astronautId}/sessions`, {
        body: {
          source: "manual", started_at: start.toISOString(), ended_at: end.toISOString(),
          exercises: [{ exercise_id: exerciseId, sets: Array.from({ length: sets }, () => ({ reps, rest_s: 60 })), notes: "" }],
          perceived_exertion: rpe, heart_rate_avg: hr ? Number(hr) : null, notes,
          client_id: `manual-${end.getTime()}`,
        },
      });
      setMsg("Workout saved and added to today's exercise minutes.");
      setNotes("");
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    }
  }
  return (
    <div className="grid g2">
      <Card title="Manual workout">
        <div className="grid g2">
          <label className="field">Exercise
            <select className="input" value={exerciseId} onChange={(e) => setExerciseId(e.target.value)}>
              {exercises.map((ex) => <option key={ex.id} value={ex.id}>{ex.name}</option>)}
            </select>
          </label>
          <label className="field">Minutes<input className="input" type="number" min={1} max={600} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} /></label>
          <label className="field">Sets<input className="input" type="number" min={1} max={20} value={sets} onChange={(e) => setSets(Number(e.target.value))} /></label>
          <label className="field">Reps per set<input className="input" type="number" min={0} max={200} value={reps} onChange={(e) => setReps(Number(e.target.value))} /></label>
          <label className="field">Effort 1–10<input className="input" type="number" min={1} max={10} value={rpe} onChange={(e) => setRpe(Number(e.target.value))} /></label>
          <label className="field">Average heart rate (optional)<input className="input" value={hr} onChange={(e) => setHr(e.target.value)} placeholder="bpm" /></label>
        </div>
        <label className="field" style={{ marginTop: 10 }}>Notes<textarea className="input" rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
        <div className="row" style={{ marginTop: 10 }}><button className="btn primary" onClick={submit}>Save workout</button></div>
        {msg && <p className="small">{msg}</p>}
        {err && <p className="err small">{err}</p>}
      </Card>
      <Card title="History">
        <div className="table-wrap">
          <table className="tbl">
            <thead><tr><th>When</th><th>Source</th><th>Min</th><th>Work</th></tr></thead>
            <tbody>
              {history.slice(0, 20).map((s) => (
                <tr key={s.id}>
                  <td>{new Date(s.started_at).toLocaleString()}</td>
                  <td>{s.source}</td>
                  <td>{s.summary?.minutes ?? ""}</td>
                  <td>{s.exercises.map((e) => e.exercise_id).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function GoalsPanel({ astronautId, goals, missed, onSaved }: { astronautId: string; goals: Goal[]; missed: string[]; onSaved: () => void }) {
  const [rows, setRows] = useState(goals);
  const [msg, setMsg] = useState("");
  async function save() {
    await api(`/exercise/astronauts/${astronautId}/goals`, {
      method: "PUT",
      body: { goals: rows.map((g) => ({ period: g.period, metric: g.metric, target: Number(g.target), label: g.label })) },
    });
    setMsg("Example targets saved.");
    onSaved();
  }
  return (
    <div className="grid g2">
      <Card title="Targets">
        {rows.map((g, i) => (
          <div key={g.period + g.metric} className="row" style={{ marginBottom: 8 }}>
            <span style={{ width: 220 }}>{g.label}</span>
            <div className="progress" style={{ flex: 1 }}><div style={{ width: `${Math.min(100, g.pct)}%` }} /></div>
            <span className="small">{g.actual}/{g.target}</span>
            <input className="input" style={{ width: 80 }} type="number" value={g.target} onChange={(e) => setRows(rows.map((r, j) => j === i ? { ...r, target: Number(e.target.value) } : r))} />
          </div>
        ))}
        <button className="btn" onClick={save}>Update targets</button>
        {msg && <p className="small">{msg}</p>}
        <p className="small faint">Daily, weekly, monthly, and yearly targets are examples. Completion is measured from this astronaut's own logs.</p>
      </Card>
      <Card title="Missed scheduled days">
        {missed.length === 0 && <div className="empty">No missed days in the recent window.</div>}
        <div className="row">{missed.slice(-14).map((d) => <Badge key={d} kind="caution">{d.slice(5)}</Badge>)}</div>
      </Card>
    </div>
  );
}
