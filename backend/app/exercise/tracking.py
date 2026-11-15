"""Pose rep-counting state machines.

Each supported exercise is a small detector: landmarks in, a phase machine out.
Add a new tracked exercise by registering a signal function and a spec entry.
Thresholds are deliberately simple and documented as unreliable outside a clear
camera view. This is not a biomechanics lab measurement.

The browser port in ``web/src/exercise/counters.ts`` must keep the same spec
numbers and phase rules.
"""
from __future__ import annotations

import math
from typing import Any

PARTIAL_DEPTH = "Partial depth. This attempt was not counted as a full repetition."
ASYMMETRY = "Left and right sides differ. Confirm the camera angle before treating this as form feedback."
LOST = "Body not fully visible. Step back so your head, hips, knees, and feet are in frame."

VISIBILITY_MIN = 0.5

# ready_when "high": a larger signal is the resting pose (knee angle).
# ready_when "low": a smaller signal is the resting pose (arms down).
SPEC: dict[str, dict[str, Any]] = {
    "squat": {
        "signal": "knee_angle",
        "ready_when": "high",
        "ready_at": 155,
        "descend_at": 145,
        "work_at": 110,
        "min_hold_ms": 80,
        "min_rep_gap_ms": 350,
        "rest_set_ms": 4000,
        "asymmetry_above": 25,
    },
    "forward_lunge": {
        "signal": "min_knee_angle",
        "ready_when": "high",
        "ready_at": 155,
        "descend_at": 145,
        "work_at": 105,
        "min_hold_ms": 80,
        "min_rep_gap_ms": 350,
        "rest_set_ms": 4000,
        "asymmetry_above": None,
    },
    "arm_raise": {
        "signal": "arm_elevation",
        "ready_when": "low",
        "ready_at": 0.03,
        "descend_at": 0.06,
        "work_at": 0.12,
        "min_hold_ms": 80,
        "min_rep_gap_ms": 350,
        "rest_set_ms": 4000,
        "asymmetry_above": 0.12,
    },
    "sumo_squat": {
        "signal": "knee_angle", "ready_when": "high", "ready_at": 155, "descend_at": 145, "work_at": 115,
        "min_hold_ms": 80, "min_rep_gap_ms": 350, "rest_set_ms": 4000, "asymmetry_above": 25,
    },
    "pushup": {   # side view: whichever elbow the camera sees best
        "signal": "elbow_angle_any", "ready_when": "high", "ready_at": 150, "descend_at": 140, "work_at": 100,
        "min_hold_ms": 80, "min_rep_gap_ms": 400, "rest_set_ms": 4000, "asymmetry_above": None,
    },
    "bicep_curl": {
        "signal": "elbow_angle", "ready_when": "high", "ready_at": 145, "descend_at": 130, "work_at": 65,
        "min_hold_ms": 80, "min_rep_gap_ms": 400, "rest_set_ms": 4000, "asymmetry_above": 40,
    },
    "shoulder_press": {   # wrists from shoulder height to overhead
        "signal": "arm_elevation", "ready_when": "low", "ready_at": 0.06, "descend_at": 0.09, "work_at": 0.2,
        "min_hold_ms": 80, "min_rep_gap_ms": 400, "rest_set_ms": 4000, "asymmetry_above": 0.12,
    },
    "jumping_jack": {   # arms from the sides to overhead
        "signal": "arm_elevation", "ready_when": "low", "ready_at": -0.05, "descend_at": 0.0, "work_at": 0.15,
        "min_hold_ms": 40, "min_rep_gap_ms": 300, "rest_set_ms": 4000, "asymmetry_above": None,
    },
    "high_knees": {   # the higher knee relative to its hip (image y grows downwards)
        "signal": "knee_lift", "ready_when": "low", "ready_at": -0.14, "descend_at": -0.11, "work_at": -0.04,
        "min_hold_ms": 40, "min_rep_gap_ms": 250, "rest_set_ms": 4000, "asymmetry_above": None,
    },
}

TRACKED_EXERCISES = tuple(SPEC)


def public_spec() -> dict[str, Any]:
    return {"version": "1.1.0", "visibility_min": VISIBILITY_MIN, "exercises": SPEC}


def angle_deg(a: dict, b: dict, c: dict) -> float | None:
    bax, bay = a["x"] - b["x"], a["y"] - b["y"]
    bcx, bcy = c["x"] - b["x"], c["y"] - b["y"]
    na, nc = math.hypot(bax, bay), math.hypot(bcx, bcy)
    if na < 1e-6 or nc < 1e-6:
        return None
    cos = max(-1.0, min(1.0, (bax * bcx + bay * bcy) / (na * nc)))
    return math.degrees(math.acos(cos))


def _pt(landmarks: dict | None, name: str) -> dict | None:
    p = (landmarks or {}).get(name)
    if not isinstance(p, dict):
        return None
    if float(p.get("visibility", 0)) < VISIBILITY_MIN:
        return None
    if "x" not in p or "y" not in p:
        return None
    return p


def _knee_angle(landmarks: dict | None, side: str) -> float | None:
    hip, knee, ankle = _pt(landmarks, f"{side}_hip"), _pt(landmarks, f"{side}_knee"), _pt(landmarks, f"{side}_ankle")
    if not hip or not knee or not ankle:
        return None
    return angle_deg(hip, knee, ankle)


def _signal(exercise_id: str, landmarks: dict | None) -> dict[str, float] | None:
    kind = SPEC[exercise_id]["signal"]
    if kind in {"knee_angle", "min_knee_angle"}:
        left, right = _knee_angle(landmarks, "left"), _knee_angle(landmarks, "right")
        if left is None or right is None:
            return None
        value = (left + right) / 2 if kind == "knee_angle" else min(left, right)
        return {"value": value, "asymmetry": abs(left - right)}
    if kind == "arm_elevation":
        elev = []
        for side in ("left", "right"):
            shoulder, wrist = _pt(landmarks, f"{side}_shoulder"), _pt(landmarks, f"{side}_wrist")
            if not shoulder or not wrist:
                return None
            elev.append(float(shoulder["y"]) - float(wrist["y"]))
        return {"value": sum(elev) / 2, "asymmetry": abs(elev[0] - elev[1])}
    if kind in {"elbow_angle", "elbow_angle_any"}:
        angles = {}
        for side in ("left", "right"):
            s, e, w = _pt(landmarks, f"{side}_shoulder"), _pt(landmarks, f"{side}_elbow"), _pt(landmarks, f"{side}_wrist")
            if s and e and w:
                a = angle_deg(s, e, w)
                if a is not None:
                    angles[side] = a
        if kind == "elbow_angle":
            if len(angles) < 2:
                return None
            return {"value": (angles["left"] + angles["right"]) / 2, "asymmetry": abs(angles["left"] - angles["right"])}
        if not angles:
            return None
        return {"value": min(angles.values()), "asymmetry": 0.0}
    if kind == "knee_lift":
        lifts = []
        for side in ("left", "right"):
            hip, knee = _pt(landmarks, f"{side}_hip"), _pt(landmarks, f"{side}_knee")
            if hip and knee:
                lifts.append(float(hip["y"]) - float(knee["y"]))
        if not lifts:
            return None
        return {"value": max(lifts), "asymmetry": 0.0}
    return None


def _leaving_ready(value: float, spec: dict) -> bool:
    if spec["ready_when"] == "high":
        return value < spec["descend_at"]
    return value > spec["descend_at"]


def _back_ready(value: float, spec: dict) -> bool:
    if spec["ready_when"] == "high":
        return value >= spec["ready_at"]
    return value <= spec["ready_at"]


def _reached_work(value: float, spec: dict) -> bool:
    if spec["ready_when"] == "high":
        return value <= spec["work_at"]
    return value >= spec["work_at"]


class RepCounter:
    """Counts repetitions for one exercise. ``update`` is called once per frame."""

    def __init__(self, exercise_id: str):
        if exercise_id not in SPEC:
            raise ValueError(f"unsupported tracked exercise '{exercise_id}'")
        self.exercise_id = exercise_id
        self.phase = "ready"
        self.reps = 0
        self.reps_in_set = 0
        self.completed_sets = 0
        self.feedback: list[str] = []
        self.form_flags: list[str] = []
        self.started = False
        self.suggest_end = False
        self.lost_ms = 0
        self.last_t: int | None = None
        self.last_rep_t: int | None = None
        self._pending: str | None = None
        self._pending_since: int | None = None
        self._depth_ok = False
        self._extreme: float | None = None

    @classmethod
    def from_state(cls, exercise_id: str, state: dict | None) -> RepCounter:
        c = cls(exercise_id)
        if not state:
            return c
        c.phase = state.get("phase", "ready")
        c.reps = int(state.get("reps", 0))
        c.reps_in_set = int(state.get("reps_in_set", 0))
        c.completed_sets = int(state.get("completed_sets", 0))
        c.feedback = list(state.get("feedback") or [])
        c.form_flags = list(state.get("form_flags") or [])
        c.started = bool(state.get("started", False))
        c.suggest_end = bool(state.get("suggest_end", False))
        c.lost_ms = int(state.get("lost_ms", 0))
        c.last_t = state.get("last_t")
        c.last_rep_t = state.get("last_rep_t")
        c._pending = state.get("pending")
        c._pending_since = state.get("pending_since")
        c._depth_ok = bool(state.get("depth_ok", False))
        c._extreme = state.get("extreme")
        return c

    def export_state(self) -> dict[str, Any]:
        return {
            "phase": self.phase, "reps": self.reps, "reps_in_set": self.reps_in_set,
            "completed_sets": self.completed_sets, "feedback": self.feedback[-3:],
            "form_flags": self.form_flags, "started": self.started, "suggest_end": self.suggest_end,
            "lost_ms": self.lost_ms, "last_t": self.last_t, "last_rep_t": self.last_rep_t,
            "pending": self._pending, "pending_since": self._pending_since,
            "depth_ok": self._depth_ok, "extreme": self._extreme,
        }

    def snapshot(self, status: str) -> dict[str, Any]:
        current_set = self.completed_sets + (1 if self.reps_in_set else 0)
        return {
            "exercise_id": self.exercise_id, "status": status, "phase": self.phase,
            "reps": self.reps, "reps_in_set": self.reps_in_set,
            "completed_sets": self.completed_sets, "current_set": current_set,
            "feedback": list(self.feedback[-3:]), "form_flags": list(self.form_flags),
            "started": self.started, "suggest_end": self.suggest_end,
        }

    def update(self, landmarks: dict | None, t_ms: int) -> dict[str, Any]:
        t_ms = int(t_ms)
        if self.last_t is not None and t_ms < self.last_t:
            t_ms = self.last_t
        sig = _signal(self.exercise_id, landmarks)
        if sig is None:
            if self.last_t is not None:
                self.lost_ms += t_ms - self.last_t
            self.last_t = t_ms
            self._pending = None
            self._pending_since = None
            if self.started and self.lost_ms >= 2500:
                self.suggest_end = True
                self.feedback = [LOST]
            return self.snapshot("tracking_lost")
        self.lost_ms = 0
        self.started = True
        self.suggest_end = False
        self.last_t = t_ms
        spec = SPEC[self.exercise_id]
        value = float(sig["value"])
        if self.phase == "attempt":
            self._extreme = value if self._extreme is None else (
                min(self._extreme, value) if spec["ready_when"] == "high" else max(self._extreme, value))
            if _reached_work(value, spec):
                self._depth_ok = True
        target = None
        if self.phase == "ready" and _leaving_ready(value, spec):
            target = "attempt"
        elif self.phase == "attempt" and _back_ready(value, spec):
            target = "ready"
        if target is None:
            self._pending = None
            self._pending_since = None
        elif self._pending != target:
            self._pending = target
            self._pending_since = t_ms
        elif self._pending_since is not None and t_ms - self._pending_since >= spec["min_hold_ms"]:
            self._commit(target, value, sig, t_ms)
            self._pending = None
            self._pending_since = None
        self._maybe_close_set(t_ms, spec)
        return self.snapshot("in_rep" if self.phase == "attempt" else "ready")

    def _commit(self, target: str, value: float, sig: dict, t_ms: int) -> None:
        spec = SPEC[self.exercise_id]
        if target == "attempt":
            self.phase = "attempt"
            self._depth_ok = _reached_work(value, spec)
            self._extreme = value
            return
        depth_ok = self._depth_ok
        self.phase = "ready"
        self._depth_ok = False
        self._extreme = None
        if not depth_ok:
            self.feedback = [PARTIAL_DEPTH]
            if PARTIAL_DEPTH not in self.form_flags:
                self.form_flags.append(PARTIAL_DEPTH)
            return
        if self.last_rep_t is not None and t_ms - self.last_rep_t < spec["min_rep_gap_ms"]:
            return
        self.reps += 1
        self.reps_in_set += 1
        self.last_rep_t = t_ms
        self.feedback = [f"Rep {self.reps}"]
        limit = spec.get("asymmetry_above")
        if limit is not None and sig.get("asymmetry", 0) > limit:
            if ASYMMETRY not in self.form_flags:
                self.form_flags.append(ASYMMETRY)

    def _maybe_close_set(self, t_ms: int, spec: dict) -> None:
        if self.phase == "ready" and self.reps_in_set > 0 and self.last_rep_t is not None:
            if t_ms - self.last_rep_t >= spec["rest_set_ms"]:
                self.completed_sets += 1
                self.reps_in_set = 0
                self.feedback = [f"Set {self.completed_sets} complete. Rest, then continue when ready."]


def run_frames(exercise_id: str, frames: list[dict]) -> dict[str, Any]:
    counter = RepCounter(exercise_id)
    snap: dict[str, Any] = counter.snapshot("ready")
    for fr in frames:
        snap = counter.update(fr.get("landmarks"), int(fr["t_ms"]))
    snap["state"] = counter.export_state()
    return snap
