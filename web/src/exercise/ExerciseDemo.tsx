import { useEffect, useRef, useState } from "react";

// Animated stick-figure example for each exercise, drawn in the sketch style.
// Each exercise is a short loop of key poses; joints are interpolated between them.
type J = "head" | "ls" | "rs" | "le" | "re" | "lw" | "rw" | "lh" | "rh" | "lk" | "rk" | "la" | "ra";
type Pose = Partial<Record<J, [number, number]>>;
type Full = Record<J, [number, number]>;

const FRONT: Full = {
  head: [50, 13], ls: [41, 25], rs: [59, 25], le: [38, 39], re: [62, 39], lw: [37, 52], rw: [63, 52],
  lh: [45, 54], rh: [55, 54], lk: [44, 71], rk: [56, 71], la: [44, 89], ra: [56, 89],
};
const side = (p: Pose): Pose => {   // side view: both limbs drawn on top of each other
  const o: Pose = { ...p };
  for (const [l, r] of [["ls", "rs"], ["le", "re"], ["lw", "rw"], ["lh", "rh"], ["lk", "rk"], ["la", "ra"]] as [J, J][]) if (o[l] && !o[r]) o[r] = o[l];
  return o;
};
const SIDE_STAND: Pose = side({ head: [50, 12], ls: [50, 25], le: [51, 38], lw: [52, 51], lh: [50, 53], lk: [51, 71], la: [50, 89] });

const LOOPS: Record<string, { view: "front" | "side"; frames: Pose[]; label: string }> = {
  squat: { view: "side", label: "side view", frames: [SIDE_STAND,
    side({ head: [47, 30], ls: [46, 42], le: [58, 44], lw: [70, 44], lh: [38, 66], lk: [56, 68], la: [50, 89] })] },
  sumo_squat: { view: "front", label: "front view", frames: [
    { lw: [47, 40], rw: [53, 40], le: [40, 42], re: [60, 42], lk: [39, 71], rk: [61, 71], la: [34, 89], ra: [66, 89] },
    { head: [50, 27], ls: [41, 39], rs: [59, 39], lw: [47, 53], rw: [53, 53], le: [40, 55], re: [60, 55], lh: [44, 67], rh: [56, 67], lk: [33, 70], rk: [67, 70], la: [34, 89], ra: [66, 89] }] },
  forward_lunge: { view: "side", label: "side view", frames: [SIDE_STAND,
    { head: [50, 27], ls: [50, 39], rs: [50, 39], le: [51, 51], re: [51, 51], lw: [52, 63], rw: [52, 63], lh: [50, 64], rh: [50, 64],
      lk: [63, 69], la: [63, 89], rk: [42, 82], ra: [31, 88] }] },
  pushup: { view: "side", label: "side view", frames: [
    side({ head: [82, 44], ls: [73, 47], le: [73, 58], lw: [73, 70], lh: [46, 55], lk: [32, 62], la: [18, 70] }),
    side({ head: [82, 58], ls: [72, 61], le: [63, 62], lw: [73, 70], lh: [46, 64], lk: [32, 67], la: [18, 70] })] },
  arm_raise: { view: "front", label: "front view", frames: [{}, { le: [29, 27], re: [71, 27], lw: [17, 26], rw: [83, 26] }] },
  shoulder_press: { view: "front", label: "front view", frames: [
    { le: [31, 34], re: [69, 34], lw: [33, 21], rw: [67, 21] },
    { le: [37, 13], re: [63, 13], lw: [40, 2], rw: [60, 2] }] },
  bicep_curl: { view: "front", label: "front view", frames: [{}, { le: [39, 39], re: [61, 39], lw: [41, 27], rw: [59, 27] }] },
  jumping_jack: { view: "front", label: "front view", frames: [{},
    { le: [33, 14], re: [67, 14], lw: [31, 3], rw: [69, 3], lk: [38, 71], rk: [62, 71], la: [32, 89], ra: [68, 89] }] },
  high_knees: { view: "front", label: "front view", frames: [{},
    { lk: [44, 55], la: [45, 72], re: [63, 34], rw: [58, 26], le: [38, 42], lw: [37, 55] }, {},
    { rk: [56, 55], ra: [55, 72], le: [37, 34], lw: [42, 26], re: [62, 42], rw: [63, 55] }] },
  brisk_march: { view: "front", label: "front view", frames: [{}, { lk: [44, 62], la: [44, 80] }, {}, { rk: [56, 62], ra: [56, 80] }] },
  calf_raise: { view: "front", label: "front view", frames: [{},
    { head: [50, 9], ls: [41, 21], rs: [59, 21], le: [38, 35], re: [62, 35], lw: [37, 48], rw: [63, 48], lh: [45, 50], rh: [55, 50], lk: [44, 67], rk: [56, 67], la: [44, 85], ra: [56, 85] }] },
  plank: { view: "side", label: "side view · hold", frames: [
    side({ head: [82, 50], ls: [73, 53], le: [73, 66], lw: [84, 68], lh: [46, 57], lk: [32, 63], la: [18, 69] }),
    side({ head: [82, 51], ls: [73, 54], le: [73, 66], lw: [84, 68], lh: [46, 58], lk: [32, 63], la: [18, 69] })] },
  glute_bridge: { view: "side", label: "side view", frames: [
    side({ head: [16, 76], ls: [26, 78], le: [36, 82], lw: [44, 84], lh: [48, 80], lk: [62, 66], la: [72, 84] }),
    side({ head: [16, 76], ls: [26, 77], le: [36, 82], lw: [44, 84], lh: [48, 64], lk: [62, 62], la: [72, 84] })] },
  shoulder_circles: { view: "front", label: "front view", frames: [{}, { ls: [41, 21], rs: [59, 21] }, { ls: [43, 25], rs: [57, 25] }, { ls: [41, 28], rs: [59, 28] }] },
};
const EDGES: [J, J][] = [["ls", "rs"], ["ls", "le"], ["le", "lw"], ["rs", "re"], ["re", "rw"], ["lh", "rh"], ["lh", "lk"], ["lk", "la"], ["rh", "rk"], ["rk", "ra"]];

function full(view: "front" | "side", p: Pose): Full {
  return { ...(view === "front" ? FRONT : (SIDE_STAND as Full)), ...p } as Full;
}

export function hasDemo(id: string) { return id in LOOPS; }

export default function ExerciseDemo({ id, size = 180 }: { id: string; size?: number }) {
  const loop = LOOPS[id] ?? LOOPS.brisk_march;
  const frames = loop.frames.map((f) => full(loop.view, f));
  const [t, setT] = useState(0);
  const raf = useRef(0);
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) { setT(0.5); return; }
    const start = performance.now();
    const tick = (now: number) => { setT(((now - start) / 1400) % frames.length); raf.current = requestAnimationFrame(tick); };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
  }, [id, frames.length]);
  const i = Math.floor(t), f = t - i;
  const e = f * f * (3 - 2 * f);
  const a = frames[i % frames.length], b = frames[(i + 1) % frames.length];
  const p = Object.fromEntries((Object.keys(a) as J[]).map((k) => [k, [a[k][0] + (b[k][0] - a[k][0]) * e, a[k][1] + (b[k][1] - a[k][1]) * e]])) as Full;
  const mid = (x: J, y: J): [number, number] => [(p[x][0] + p[y][0]) / 2, (p[x][1] + p[y][1]) / 2];
  const [nx, ny] = mid("ls", "rs"), [hx, hy] = mid("lh", "rh");
  return (
    <figure className="ex-demo" style={{ width: size }}>
      <svg viewBox="0 0 100 100" role="img" aria-label={`Example of ${id.replace(/_/g, " ")}`}>
        <line x1="4" y1="92" x2="96" y2="92" className="ex-demo-floor" />
        <line x1={nx} y1={ny} x2={hx} y2={hy} className="ex-demo-bone" />
        {EDGES.map(([x, y]) => <line key={x + y} x1={p[x][0]} y1={p[x][1]} x2={p[y][0]} y2={p[y][1]} className="ex-demo-bone" />)}
        <circle cx={p.head[0]} cy={p.head[1]} r="6" className="ex-demo-head" />
        {(["lw", "rw", "la", "ra", "lk", "rk", "le", "re"] as J[]).map((k) => <circle key={k} cx={p[k][0]} cy={p[k][1]} r="1.8" className="ex-demo-joint" />)}
      </svg>
      <figcaption>{loop.label}</figcaption>
    </figure>
  );
}
