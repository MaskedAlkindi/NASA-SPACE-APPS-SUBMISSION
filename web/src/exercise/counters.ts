/** Browser port of backend/app/exercise/tracking.py. Keep the phase rules aligned. */

export type Point = { x: number; y: number; visibility?: number };
export type Landmarks = Record<string, Point>;

export type TrackingSpec = {
  signal: "knee_angle" | "min_knee_angle" | "arm_elevation" | "elbow_angle" | "elbow_angle_any" | "knee_lift";
  ready_when: "high" | "low";
  ready_at: number;
  descend_at: number;
  work_at: number;
  min_hold_ms: number;
  min_rep_gap_ms: number;
  rest_set_ms: number;
  asymmetry_above: number | null;
};

export const FALLBACK_SPEC: Record<string, TrackingSpec> = {
  squat: { signal: "knee_angle", ready_when: "high", ready_at: 155, descend_at: 145, work_at: 110, min_hold_ms: 80, min_rep_gap_ms: 350, rest_set_ms: 4000, asymmetry_above: 25 },
  forward_lunge: { signal: "min_knee_angle", ready_when: "high", ready_at: 155, descend_at: 145, work_at: 105, min_hold_ms: 80, min_rep_gap_ms: 350, rest_set_ms: 4000, asymmetry_above: null },
  arm_raise: { signal: "arm_elevation", ready_when: "low", ready_at: 0.03, descend_at: 0.06, work_at: 0.12, min_hold_ms: 80, min_rep_gap_ms: 350, rest_set_ms: 4000, asymmetry_above: 0.12 },
  sumo_squat: { signal: "knee_angle", ready_when: "high", ready_at: 155, descend_at: 145, work_at: 115, min_hold_ms: 80, min_rep_gap_ms: 350, rest_set_ms: 4000, asymmetry_above: 25 },
  pushup: { signal: "elbow_angle_any", ready_when: "high", ready_at: 150, descend_at: 140, work_at: 100, min_hold_ms: 80, min_rep_gap_ms: 400, rest_set_ms: 4000, asymmetry_above: null },
  bicep_curl: { signal: "elbow_angle", ready_when: "high", ready_at: 145, descend_at: 130, work_at: 65, min_hold_ms: 80, min_rep_gap_ms: 400, rest_set_ms: 4000, asymmetry_above: 40 },
  shoulder_press: { signal: "arm_elevation", ready_when: "low", ready_at: 0.06, descend_at: 0.09, work_at: 0.2, min_hold_ms: 80, min_rep_gap_ms: 400, rest_set_ms: 4000, asymmetry_above: 0.12 },
  jumping_jack: { signal: "arm_elevation", ready_when: "low", ready_at: -0.05, descend_at: 0.0, work_at: 0.15, min_hold_ms: 40, min_rep_gap_ms: 300, rest_set_ms: 4000, asymmetry_above: null },
  high_knees: { signal: "knee_lift", ready_when: "low", ready_at: -0.14, descend_at: -0.11, work_at: -0.04, min_hold_ms: 40, min_rep_gap_ms: 250, rest_set_ms: 4000, asymmetry_above: null },
};

const PARTIAL = "Partial depth. This attempt was not counted as a full repetition.";
const ASYMMETRY = "Left and right sides differ. Confirm the camera angle before treating this as form feedback.";
const LOST = "Body not fully visible. Step back so your head, hips, knees, and feet are in frame.";

export type Snapshot = {
  exercise_id: string;
  status: string;
  phase: string;
  reps: number;
  reps_in_set: number;
  completed_sets: number;
  current_set: number;
  feedback: string[];
  form_flags: string[];
  started: boolean;
  suggest_end: boolean;
};

export function angleDeg(a: Point, b: Point, c: Point): number | null {
  const bax = a.x - b.x, bay = a.y - b.y, bcx = c.x - b.x, bcy = c.y - b.y;
  const na = Math.hypot(bax, bay), nc = Math.hypot(bcx, bcy);
  if (na < 1e-6 || nc < 1e-6) return null;
  const cos = Math.max(-1, Math.min(1, (bax * bcx + bay * bcy) / (na * nc)));
  return (Math.acos(cos) * 180) / Math.PI;
}

function pt(landmarks: Landmarks | null, name: string, minVis: number): Point | null {
  const p = landmarks?.[name];
  if (!p || (p.visibility ?? 0) < minVis) return null;
  return p;
}

function knee(landmarks: Landmarks | null, side: string, minVis: number): number | null {
  const hip = pt(landmarks, `${side}_hip`, minVis);
  const kneePt = pt(landmarks, `${side}_knee`, minVis);
  const ankle = pt(landmarks, `${side}_ankle`, minVis);
  if (!hip || !kneePt || !ankle) return null;
  return angleDeg(hip, kneePt, ankle);
}

function signal(spec: TrackingSpec, landmarks: Landmarks | null, minVis: number): { value: number; asymmetry: number } | null {
  if (spec.signal === "knee_angle" || spec.signal === "min_knee_angle") {
    const left = knee(landmarks, "left", minVis);
    const right = knee(landmarks, "right", minVis);
    if (left == null || right == null) return null;
    return { value: spec.signal === "knee_angle" ? (left + right) / 2 : Math.min(left, right), asymmetry: Math.abs(left - right) };
  }
  if (spec.signal === "elbow_angle" || spec.signal === "elbow_angle_any") {
    const angles: number[] = [];
    for (const side of ["left", "right"]) {
      const s = pt(landmarks, `${side}_shoulder`, minVis), e = pt(landmarks, `${side}_elbow`, minVis), w = pt(landmarks, `${side}_wrist`, minVis);
      const a = s && e && w ? angleDeg(s, e, w) : null;
      if (a != null) angles.push(a);
    }
    if (spec.signal === "elbow_angle") return angles.length === 2 ? { value: (angles[0] + angles[1]) / 2, asymmetry: Math.abs(angles[0] - angles[1]) } : null;
    return angles.length ? { value: Math.min(...angles), asymmetry: 0 } : null;
  }
  if (spec.signal === "knee_lift") {
    const lifts: number[] = [];
    for (const side of ["left", "right"]) {
      const hip = pt(landmarks, `${side}_hip`, minVis), k = pt(landmarks, `${side}_knee`, minVis);
      if (hip && k) lifts.push(hip.y - k.y);
    }
    return lifts.length ? { value: Math.max(...lifts), asymmetry: 0 } : null;
  }
  const elev: number[] = [];
  for (const side of ["left", "right"]) {
    const shoulder = pt(landmarks, `${side}_shoulder`, minVis);
    const wrist = pt(landmarks, `${side}_wrist`, minVis);
    if (!shoulder || !wrist) return null;
    elev.push(shoulder.y - wrist.y);
  }
  return { value: (elev[0] + elev[1]) / 2, asymmetry: Math.abs(elev[0] - elev[1]) };
}

export class RepCounter {
  phase = "ready";
  reps = 0;
  repsInSet = 0;
  completedSets = 0;
  feedback: string[] = [];
  formFlags: string[] = [];
  started = false;
  suggestEnd = false;
  lostMs = 0;
  lastT: number | null = null;
  lastRepT: number | null = null;
  private pending: string | null = null;
  private pendingSince: number | null = null;
  private depthOk = false;
  private extreme: number | null = null;

  constructor(readonly exerciseId: string, readonly spec: TrackingSpec, readonly minVis = 0.5) {}

  snapshot(status: string): Snapshot {
    return {
      exercise_id: this.exerciseId, status, phase: this.phase, reps: this.reps,
      reps_in_set: this.repsInSet, completed_sets: this.completedSets,
      current_set: this.completedSets + (this.repsInSet ? 1 : 0),
      feedback: this.feedback.slice(-3), form_flags: [...this.formFlags],
      started: this.started, suggest_end: this.suggestEnd,
    };
  }

  update(landmarks: Landmarks | null, tMs: number): Snapshot {
    let t = tMs;
    if (this.lastT != null && t < this.lastT) t = this.lastT;
    const sig = signal(this.spec, landmarks, this.minVis);
    if (!sig) {
      if (this.lastT != null) this.lostMs += t - this.lastT;
      this.lastT = t;
      this.pending = null;
      this.pendingSince = null;
      if (this.started && this.lostMs >= 2500) {
        this.suggestEnd = true;
        this.feedback = [LOST];
      }
      return this.snapshot("tracking_lost");
    }
    this.lostMs = 0;
    this.started = true;
    this.suggestEnd = false;
    this.lastT = t;
    const value = sig.value;
    if (this.phase === "attempt") {
      this.extreme = this.extreme == null ? value : (this.spec.ready_when === "high" ? Math.min(this.extreme, value) : Math.max(this.extreme, value));
      if (reachedWork(value, this.spec)) this.depthOk = true;
    }
    let target: string | null = null;
    if (this.phase === "ready" && leaving(value, this.spec)) target = "attempt";
    else if (this.phase === "attempt" && backReady(value, this.spec)) target = "ready";
    if (target == null) {
      this.pending = null;
      this.pendingSince = null;
    } else if (this.pending !== target) {
      this.pending = target;
      this.pendingSince = t;
    } else if (this.pendingSince != null && t - this.pendingSince >= this.spec.min_hold_ms) {
      this.commit(target, value, sig, t);
      this.pending = null;
      this.pendingSince = null;
    }
    this.maybeClose(t);
    return this.snapshot(this.phase === "attempt" ? "in_rep" : "ready");
  }

  private commit(target: string, value: number, sig: { asymmetry: number }, t: number) {
    if (target === "attempt") {
      this.phase = "attempt";
      this.depthOk = reachedWork(value, this.spec);
      this.extreme = value;
      return;
    }
    const depthOk = this.depthOk;
    this.phase = "ready";
    this.depthOk = false;
    this.extreme = null;
    if (!depthOk) {
      this.feedback = [PARTIAL];
      if (!this.formFlags.includes(PARTIAL)) this.formFlags.push(PARTIAL);
      return;
    }
    if (this.lastRepT != null && t - this.lastRepT < this.spec.min_rep_gap_ms) return;
    this.reps += 1;
    this.repsInSet += 1;
    this.lastRepT = t;
    this.feedback = [`Rep ${this.reps}`];
    if (this.spec.asymmetry_above != null && sig.asymmetry > this.spec.asymmetry_above && !this.formFlags.includes(ASYMMETRY)) {
      this.formFlags.push(ASYMMETRY);
    }
  }

  private maybeClose(t: number) {
    if (this.phase === "ready" && this.repsInSet > 0 && this.lastRepT != null && t - this.lastRepT >= this.spec.rest_set_ms) {
      this.completedSets += 1;
      this.repsInSet = 0;
      this.feedback = [`Set ${this.completedSets} complete. Rest, then continue when ready.`];
    }
  }
}

function leaving(value: number, spec: TrackingSpec) {
  return spec.ready_when === "high" ? value < spec.descend_at : value > spec.descend_at;
}
function backReady(value: number, spec: TrackingSpec) {
  return spec.ready_when === "high" ? value >= spec.ready_at : value <= spec.ready_at;
}
function reachedWork(value: number, spec: TrackingSpec) {
  return spec.ready_when === "high" ? value <= spec.work_at : value >= spec.work_at;
}

export const POSE_INDEX: Record<string, number> = {
  nose: 0, left_shoulder: 11, right_shoulder: 12, left_elbow: 13, right_elbow: 14,
  left_wrist: 15, right_wrist: 16, left_hip: 23, right_hip: 24, left_knee: 25,
  right_knee: 26, left_ankle: 27, right_ankle: 28,
};

const EDGES: [string, string][] = [
  ["left_shoulder", "right_shoulder"], ["left_shoulder", "left_elbow"], ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"], ["right_elbow", "right_wrist"], ["left_shoulder", "left_hip"],
  ["right_shoulder", "right_hip"], ["left_hip", "right_hip"], ["left_hip", "left_knee"],
  ["left_knee", "left_ankle"], ["right_hip", "right_knee"], ["right_knee", "right_ankle"],
];

export function landmarksFromPose(pose: { x: number; y: number; visibility?: number }[]): Landmarks {
  const out: Landmarks = {};
  for (const [name, index] of Object.entries(POSE_INDEX)) {
    const p = pose[index];
    if (!p) continue;
    out[name] = { x: p.x, y: p.y, visibility: p.visibility ?? 0 };
  }
  return out;
}

export function drawPose(ctx: CanvasRenderingContext2D, landmarks: Landmarks, w: number, h: number) {
  ctx.clearRect(0, 0, w, h);
  ctx.lineWidth = 3;
  ctx.strokeStyle = "#6c9cff";
  ctx.fillStyle = "#d81b1b";
  for (const [a, b] of EDGES) {
    const pa = landmarks[a], pb = landmarks[b];
    if (!pa || !pb) continue;
    ctx.beginPath();
    ctx.moveTo(pa.x * w, pa.y * h);
    ctx.lineTo(pb.x * w, pb.y * h);
    ctx.stroke();
  }
  for (const p of Object.values(landmarks)) {
    ctx.beginPath();
    ctx.arc(p.x * w, p.y * h, 4, 0, Math.PI * 2);
    ctx.fill();
  }
}

export function chooseStrategy(input: {
  cameraPermission: "granted" | "denied" | "prompt";
  localPose: "ready" | "failed" | "unavailable";
  remoteConfigured: boolean;
  remoteConsent: boolean;
  remoteStatus: "ready" | "failed" | "skipped";
}): { strategy: "local" | "remote" | "manual"; reason: string } {
  if (input.cameraPermission === "denied") return { strategy: "manual", reason: "Camera permission was denied. Log the workout manually." };
  if (input.localPose === "ready") return { strategy: "local", reason: "Pose detection is running in this browser. Video stays on the device." };
  if (input.remoteConfigured && input.remoteConsent && input.remoteStatus === "ready") {
    return { strategy: "remote", reason: "Using the configured inference service. You consented to send frames or landmarks for this session." };
  }
  if (input.localPose === "failed" && input.remoteConfigured && input.remoteConsent && input.remoteStatus === "failed") {
    return { strategy: "manual", reason: "On-device pose detection failed and the inference service did not respond. Log the workout manually." };
  }
  if (input.localPose === "failed" || input.localPose === "unavailable") {
    if (input.remoteConfigured && !input.remoteConsent) {
      return { strategy: "manual", reason: "On-device pose detection is unavailable. Remote processing stays off until you allow it. Log the workout manually or allow remote processing." };
    }
    return { strategy: "manual", reason: "On-device pose detection is unavailable and no inference service is ready. Log the workout manually." };
  }
  return { strategy: "manual", reason: "Camera tracking is not ready. Log the workout manually." };
}
