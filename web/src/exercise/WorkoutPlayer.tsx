import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Badge } from "../components/ui";
import CameraPanel from "./CameraPanel";
import ExerciseDemo from "./ExerciseDemo";

type Item = { exercise_id: string; name: string; sets: number; reps: number | null; duration_s: number | null; rest_s: number; intensity: string };
type Ex = { id: string; name: string; tracking: string | null; cues: string[]; steps?: string[] };

/** Step-by-step guided workout: one exercise at a time, sets, rest timer, optional camera counting, save at the end. */
export default function WorkoutPlayer({ items, catalog, astronautId, onClose, onSaved }: {
  items: Item[]; catalog: Ex[]; astronautId: string; onClose: () => void; onSaved: () => void;
}) {
  const [idx, setIdx] = useState(0);
  const [set, setSet] = useState(1);
  const [phase, setPhase] = useState<"work" | "rest" | "done">("work");
  const [left, setLeft] = useState(0);
  const [camera, setCamera] = useState(false);
  const [byCamera, setByCamera] = useState<Set<string>>(new Set());
  const [done, setDone] = useState<Record<string, number>>({});
  const [started] = useState(() => new Date());
  const [msg, setMsg] = useState("");
  const item = items[idx];
  const ex = useMemo(() => catalog.find((e) => e.id === item?.exercise_id), [catalog, item]);
  const totalSets = items.reduce((a, it) => a + it.sets, 0);
  const doneSets = Object.values(done).reduce((a, n) => a + n, 0);

  useEffect(() => {   // countdown for rest and for timed holds
    if (left <= 0) return;
    const t = setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [left]);
  useEffect(() => { if (phase === "rest" && left === 0) setPhase("work"); }, [phase, left]);

  function finishSet() {
    setDone((d) => ({ ...d, [item.exercise_id]: (d[item.exercise_id] ?? 0) + 1 }));
    if (set < item.sets) { setSet(set + 1); setPhase("rest"); setLeft(item.rest_s || 30); return; }
    next();
  }
  function next() {
    setCamera(false);
    if (idx + 1 < items.length) { setIdx(idx + 1); setSet(1); setPhase("rest"); setLeft(items[idx].rest_s || 30); }
    else setPhase("done");
  }
  async function save() {
    const exercises = items.filter((it) => (done[it.exercise_id] ?? 0) > 0 && !byCamera.has(it.exercise_id)).map((it) => ({
      exercise_id: it.exercise_id,
      sets: Array.from({ length: done[it.exercise_id] }, () => (it.reps ? { reps: it.reps, rest_s: it.rest_s } : { duration_s: it.duration_s, rest_s: it.rest_s })),
      notes: "",
    }));
    if (!exercises.length) { setMsg("Camera sessions are already saved."); onSaved(); return; }
    try {
      await api(`/exercise/astronauts/${astronautId}/sessions`, { body: {
        source: "manual", started_at: started.toISOString(), ended_at: new Date().toISOString(), exercises,
        notes: "Guided workout", client_id: `guided-${started.getTime()}` } });
      setMsg("Workout saved."); onSaved();
    } catch (e) { setMsg(e instanceof Error ? e.message : "Save failed"); }
  }

  if (!items.length) return <div className="empty">No exercises in today's plan.</div>;
  return (
    <div className="player card">
      <div className="player-top">
        <b>Guided workout</b>
        <div className="progress" style={{ flex: 1 }}><div style={{ width: `${(100 * doneSets) / totalSets}%` }} /></div>
        <span className="small mono">{doneSets}/{totalSets} sets</span>
        <button className="btn ghost" onClick={onClose}>Close</button>
      </div>

      {phase === "done" ? (
        <div className="player-done">
          <h2>Workout complete</h2>
          <p className="muted">{doneSets} sets across {Object.keys(done).length} exercises in {Math.round((Date.now() - started.getTime()) / 60000)} min.</p>
          <div className="row"><button className="btn primary big-btn" onClick={save}>Save workout</button><button className="btn" onClick={onClose}>Close</button></div>
          {msg && <p className="small">{msg}</p>}
        </div>
      ) : (
        <div className="player-body">
          <div className="player-demo">
            <ExerciseDemo id={item.exercise_id} size={220} />
          </div>
          <div className="player-info">
            <span className="ex-kicker">Exercise {idx + 1} of {items.length}{ex?.tracking ? " · camera" : ""}</span>
            <h2>{item.name}</h2>
            <div className="player-target">
              <span className="ex-dose">Set {set} of {item.sets}</span>
              <span className="ex-dose">{item.reps ? `${item.reps} reps` : `${item.duration_s}s hold`}</span>
              <Badge kind="neutral">{item.intensity}</Badge>
            </div>
            {phase === "rest" ? (
              <div className="player-rest">
                <span className="ex-kicker">Rest</span>
                <b className="mono">{left}s</b>
                <button className="btn" onClick={() => setLeft(0)}>Skip rest</button>
              </div>
            ) : (
              <>
                <ol className="player-steps">{(ex?.steps?.length ? ex.steps : ex?.cues ?? []).map((s) => <li key={s}>{s}</li>)}</ol>
                <div className="row">
                  {!item.reps && item.duration_s ? (
                    left > 0 ? <span className="mono big">{left}s</span>
                      : <button className="btn" onClick={() => setLeft(item.duration_s ?? 30)}>Start {item.duration_s}s timer</button>
                  ) : null}
                  <button className="btn primary big-btn" onClick={finishSet}>✓ Set done</button>
                  {ex?.tracking && <button className="btn" onClick={() => setCamera(!camera)}>{camera ? "Hide camera" : "Count with camera"}</button>}
                  <button className="btn ghost" onClick={next}>Skip exercise</button>
                </div>
              </>
            )}
            {ex?.cues?.[0] && phase !== "rest" && <p className="small faint">{ex.cues.join(" ")}</p>}
          </div>
          {camera && ex?.tracking && phase === "work" && (
            <div className="player-camera">
              <CameraPanel astronautId={astronautId} initialExercise={item.exercise_id} lockExercise compact
                onSaved={() => { setByCamera((s) => new Set(s).add(item.exercise_id)); finishSet(); }} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
