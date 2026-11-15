import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { AstronautPicker, useSelectedAstronaut } from "../components/AstronautPicker";
import { Badge, Card, Loading, chartTooltip } from "../components/ui";

type Mark = { key: string; label: string; unit: string; mark: number; kind: "floor" | "ceiling" };
type Meal = {
  id: number; name: string; meal: string; eaten_at: string | null; notes: string; data_class: string;
  kcal: number; protein_g: number; carb_g: number; fat_g: number; fluid_ml: number;
  sodium_mg: number; calcium_mg: number; iron_mg: number; vitamin_d_iu: number;
};
type Food = Omit<Meal, "id" | "eaten_at" | "notes" | "data_class"> & { id: string };
type Fact = { text: string; source: string; href: string };
type Day = {
  date: string; disclaimer: string; marks: Mark[]; facts: Fact[];
  totals: Record<string, number>; meals: Meal[];
  mass: { kg: number; logged_on: string; note: string; data_class: string } | null;
  latest_mass: { kg: number; logged_on: string; data_class: string } | null;
};
type History = { days: { date: string; kcal: number; fluid_ml: number; protein_g: number }[]; mass: { date: string; kg: number }[] };

const EMPTY = { name: "", meal: "snack", kcal: "", protein_g: "", fluid_ml: "", sodium_mg: "", calcium_mg: "", iron_mg: "", vitamin_d_iu: "" };

function utcToday() {
  return new Date().toISOString().slice(0, 10);
}
function shift(day: string, by: number) {
  const d = new Date(`${day}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + by);
  return d.toISOString().slice(0, 10);
}
function num(v: string) {
  const n = Number(v);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

function Ring({ pct, label, sub, over }: { pct: number; label: string; sub: string; over?: boolean }) {
  const r = 36, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, pct));
  return (
    <div className="ring">
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle cx="50" cy="50" r={r} className="ring-bg" />
        <circle cx="50" cy="50" r={r} className="ring-fg" stroke={over ? "var(--caution)" : undefined} strokeDasharray={`${(v / 100) * c} ${c}`} transform="rotate(-90 50 50)" />
      </svg>
      <div className="ring-text"><b>{Math.round(pct)}%</b><span>{label}</span></div>
      <small>{sub}</small>
    </div>
  );
}

export default function NutritionPage() {
  const { crew, selected, select, current } = useSelectedAstronaut();
  const [day, setDay] = useState(utcToday);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [kg, setKg] = useState("");
  const [tick, setTick] = useState(0);
  const id = selected;

  const [data, setData] = useState<Day | null>(null);
  const [history, setHistory] = useState<History | null>(null);
  const [foods, setFoods] = useState<Food[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    const ctl = new AbortController();
    setLoading(true);
    setErr(null);
    Promise.all([
      api<Day>(`/nutrition/astronauts/${id}/day?on=${day}`, { signal: ctl.signal }),
      api<History>(`/nutrition/astronauts/${id}/history?days=14`, { signal: ctl.signal }),
      api<{ foods: Food[] }>("/nutrition/foods", { signal: ctl.signal }),
    ]).then(([d, h, f]) => {
      setData(d);
      setHistory(h);
      setFoods(f.foods);
      setKg(d.mass ? String(d.mass.kg) : d.latest_mass ? String(d.latest_mass.kg) : "");
      setLoading(false);
    }).catch((e) => {
      if (e?.name === "AbortError") return;
      setErr(e.message);
      setLoading(false);
    });
    return () => ctl.abort();
  }, [id, day, tick]);

  const rings = useMemo(() => {
    if (!data) return [];
    return data.marks.map((m) => {
      const got = data.totals[m.key] ?? 0;
      const pct = m.mark ? (got / m.mark) * 100 : 0;
      const over = m.kind === "ceiling" && got > m.mark;
      return { ...m, got, pct: m.kind === "ceiling" ? Math.min(pct, 100) : pct, over };
    });
  }, [data]);

  const headline = useMemo(() => {
    if (!data) return ["Checking the day", "neutral"];
    const over = rings.filter((r) => r.over);
    if (over.length) return [`${over.map((r) => r.label).join(" and ")} over the example ceiling`, "caution"];
    const fluid = rings.find((r) => r.key === "fluid_ml");
    if (fluid && fluid.pct < 50) return ["Fluid is behind the example mark", "caution"];
    const energy = rings.find((r) => r.key === "kcal");
    if (energy && energy.pct >= 80) return ["The day is mostly filled in", "ok"];
    return ["Still room on the example marks", "neutral"];
  }, [data, rings]);

  async function addMeal(partial: Partial<Food> & { name: string; meal: string }) {
    if (!id) return;
    setBusy(true);
    setErr(null);
    try {
      await api(`/nutrition/astronauts/${id}/meals`, {
        body: { ...partial, eaten_at: `${day}T12:00:00Z` },
      });
      setForm(EMPTY);
      setTick((n) => n + 1);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save the meal");
    } finally {
      setBusy(false);
    }
  }

  async function saveMass() {
    if (!id || !kg) return;
    setBusy(true);
    setErr(null);
    try {
      await api(`/nutrition/astronauts/${id}/mass`, { method: "PUT", body: { kg: Number(kg), logged_on: day } });
      setTick((n) => n + 1);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not save body mass");
    } finally {
      setBusy(false);
    }
  }

  async function remove(mealId: number) {
    if (!id) return;
    setBusy(true);
    try {
      await api(`/nutrition/astronauts/${id}/meals/${mealId}`, { method: "DELETE" });
      setTick((n) => n + 1);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not remove that meal");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Nutrition</h1>
          <p>Food, fluid and body mass for {current?.callsign ?? "the crew"}. The rings use example marks so a short day is easy to see. They are not a flight menu.</p>
        </div>
        <div className="spacer" />
        <AstronautPicker crew={crew} selected={selected} onSelect={select} />
      </div>

      <div className="row" style={{ margin: "8px 0 14px" }}>
        <button type="button" className="btn" onClick={() => setDay(shift(day, -1))}>← previous day</button>
        <b>{day}</b>
        <span className="small muted">station day, UTC</span>
        <button type="button" className="btn" onClick={() => setDay(shift(day, 1))} disabled={day >= utcToday()}>next day →</button>
        {day !== utcToday() && <button type="button" className="btn" onClick={() => setDay(utcToday())}>today</button>}
      </div>

      {!id && <Loading what="Nutrition" />}
      {err && <div className="err">{err}</div>}
      {id && loading && !data && <Loading what="the food log" />}

      {data && (
        <>
          <section className={`ex-hero ${headline[1]}`}>
            <div className="ex-ready">
              <span className="ex-kicker">This station day</span>
              <h2>{headline[0]}</h2>
              <p>
                {data.latest_mass
                  ? `Last body mass on file: ${data.latest_mass.kg} kg (${data.latest_mass.logged_on}). NASA's nutrition report puts average loss near 2.4% of body weight per 100 days.`
                  : "No body mass yet. A scale reading makes the slow loss visible."}
              </p>
              <p className="small faint" style={{ marginTop: 10 }}>{data.disclaimer}</p>
            </div>
            <div className="nut-rings">
              {rings.filter((r) => ["kcal", "protein_g", "fluid_ml", "calcium_mg"].includes(r.key)).map((r) => (
                <Ring key={r.key} pct={r.pct} label={r.label} over={r.over} sub={`${Math.round(r.got)} / ${r.mark} ${r.unit}`} />
              ))}
            </div>
          </section>

          <div className="grid g4" style={{ marginTop: 14 }}>
            {rings.map((r) => (
              <div key={r.key} className={`tile ${r.over ? "concern" : ""}`}>
                <div className="label">{r.label} {r.kind === "ceiling" && <Badge kind="neutral">ceiling</Badge>}</div>
                <div className="value">{Math.round(r.got)} <span className="small muted">{r.unit}</span></div>
                <div className="sub">{r.kind === "ceiling" ? `example ceiling ${r.mark}` : `example mark ${r.mark}`} {r.unit}</div>
              </div>
            ))}
          </div>

          <div className="grid g2" style={{ marginTop: 14 }}>
            <Card title="Log a meal" extra={<Badge kind="info">your entry</Badge>}>
              <div className="row" style={{ flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
                {foods.map((f) => (
                  <button key={f.id} type="button" className="btn" disabled={busy} onClick={() => addMeal(f)}>{f.name}</button>
                ))}
              </div>
              <p className="small faint" style={{ marginTop: 0 }}>Those buttons are example portions, so a demo day can be filled in. They are not a lab analysis of flight food.</p>
              <form onSubmit={(e) => { e.preventDefault(); if (form.name.trim()) addMeal({ name: form.name.trim(), meal: form.meal, kcal: num(form.kcal), protein_g: num(form.protein_g), fluid_ml: num(form.fluid_ml), sodium_mg: num(form.sodium_mg), calcium_mg: num(form.calcium_mg), iron_mg: num(form.iron_mg), vitamin_d_iu: num(form.vitamin_d_iu), carb_g: 0, fat_g: 0 }); }}>
                <div className="grid g2">
                  <label className="field">Name<input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
                  <label className="field">When
                    <select className="input" value={form.meal} onChange={(e) => setForm({ ...form, meal: e.target.value })}>
                      {["breakfast", "lunch", "dinner", "snack", "drink"].map((m) => <option key={m}>{m}</option>)}
                    </select>
                  </label>
                  <label className="field">kcal<input className="input" inputMode="decimal" value={form.kcal} onChange={(e) => setForm({ ...form, kcal: e.target.value })} /></label>
                  <label className="field">protein, g<input className="input" inputMode="decimal" value={form.protein_g} onChange={(e) => setForm({ ...form, protein_g: e.target.value })} /></label>
                  <label className="field">fluid, mL<input className="input" inputMode="decimal" value={form.fluid_ml} onChange={(e) => setForm({ ...form, fluid_ml: e.target.value })} /></label>
                  <label className="field">sodium, mg<input className="input" inputMode="decimal" value={form.sodium_mg} onChange={(e) => setForm({ ...form, sodium_mg: e.target.value })} /></label>
                  <label className="field">calcium, mg<input className="input" inputMode="decimal" value={form.calcium_mg} onChange={(e) => setForm({ ...form, calcium_mg: e.target.value })} /></label>
                  <label className="field">iron, mg<input className="input" inputMode="decimal" value={form.iron_mg} onChange={(e) => setForm({ ...form, iron_mg: e.target.value })} /></label>
                  <label className="field">vitamin D, IU<input className="input" inputMode="decimal" value={form.vitamin_d_iu} onChange={(e) => setForm({ ...form, vitamin_d_iu: e.target.value })} /></label>
                </div>
                <button className="btn primary" style={{ marginTop: 12 }} disabled={busy || !form.name.trim()}>Add to this day</button>
              </form>
            </Card>

            <Card title={`Eaten on ${day}`} extra={<span className="small muted">{data.meals.length} items</span>}>
              {data.meals.length === 0 && <div className="empty">Nothing logged this station day.</div>}
              <div className="col">
                {data.meals.map((m) => (
                  <div key={m.id} className="ex-sug">
                    <div className="row">
                      <b>{m.name}</b>
                      <Badge kind="neutral">{m.meal}</Badge>
                      <Badge kind={m.data_class === "simulated" ? "sim" : "real"}>{m.data_class === "simulated" ? "example" : "entered"}</Badge>
                      <div className="spacer" />
                      <button type="button" className="btn ghost" disabled={busy} onClick={() => remove(m.id)}>remove</button>
                    </div>
                    <span className="small muted">{Math.round(m.kcal)} kcal · {m.protein_g} g protein · {Math.round(m.fluid_ml)} mL · {Math.round(m.sodium_mg)} mg sodium</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card title="Body mass">
              <p className="small">One number for this station day. The nutrition evidence report is why it is here: crews lose mass when intake falls short, about 2.4% per 100 days on average.</p>
              <div className="row" style={{ marginTop: 10 }}>
                <label className="field">kg<input className="input" inputMode="decimal" value={kg} onChange={(e) => setKg(e.target.value)} /></label>
                <button type="button" className="btn primary" disabled={busy || !kg} onClick={saveMass}>Save</button>
              </div>
              {history && history.mass.length > 1 && (
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={history.mass}>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="date" tickFormatter={(d) => String(d).slice(5)} minTickGap={16} />
                    <YAxis domain={["dataMin - 1", "dataMax + 1"]} />
                    <Tooltip {...chartTooltip} />
                    <Bar dataKey="kg" fill="var(--steel)" name="kg" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </Card>

            <Card title="Energy, last 14 station days">
              {history ? (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={history.days}>
                    <CartesianGrid vertical={false} />
                    <XAxis dataKey="date" tickFormatter={(d) => String(d).slice(5)} minTickGap={16} />
                    <YAxis />
                    <Tooltip {...chartTooltip} />
                    <Bar dataKey="kcal" fill="var(--steel)" name="kcal" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : <Loading what="History" />}
            </Card>
          </div>

          <Card title="Why these numbers are on the page" className="" >
            <ul className="small">
              {data.facts.map((f) => (
                <li key={f.href} style={{ marginBottom: 8 }}>
                  {f.text}{" "}
                  <a href={f.href} target="_blank" rel="noreferrer">{f.source}</a>
                </li>
              ))}
            </ul>
            <p className="small faint">The rings are example marks chosen for this demo so a day has a scale. NASA does not publish one menu that fits every astronaut. Inadequate food and nutrition is an HRP risk: <a href="https://www.nasa.gov/reference/risk-of-inadequate-food-and-nutrition/" target="_blank" rel="noreferrer">the risk page</a>.</p>
          </Card>
        </>
      )}
    </>
  );
}
