from app.exercise.catalog import CATALOG
from app.exercise.tracking import SPEC, run_frames


def _frames(make, pattern, reps=3, dt=60):
    out, t = [], 0
    for _ in range(reps):
        for state in pattern:
            out.append({"t_ms": t, "landmarks": make(state)})
            t += dt
    return out


def _arms(bent: bool, up: float = 0.0):
    d = {}
    for side, x in (("left", .45), ("right", .55)):
        d[f"{side}_shoulder"] = {"x": x, "y": .30, "visibility": 1}
        d[f"{side}_elbow"] = {"x": x, "y": .45 - up, "visibility": 1}
        d[f"{side}_wrist"] = {"x": x + (.12 if bent else 0), "y": (.35 if bent else .60) - 2 * up, "visibility": 1}
    return d


def _legs(lift: str | None):
    d = {}
    for side, x in (("left", .45), ("right", .55)):
        d[f"{side}_hip"] = {"x": x, "y": .55, "visibility": 1}
        d[f"{side}_knee"] = {"x": x, "y": .57 if lift == side else .72, "visibility": 1}
    return d


def test_new_tracked_movements_count():
    assert {"pushup", "bicep_curl", "shoulder_press", "jumping_jack", "high_knees", "sumo_squat"} <= set(SPEC)
    assert run_frames("bicep_curl", _frames(_arms, [False] * 4 + [True] * 4 + [False] * 4))["reps"] == 3
    assert run_frames("pushup", _frames(_arms, [False] * 4 + [True] * 4 + [False] * 4))["reps"] == 3
    knees = _frames(_legs, [None] * 4 + ["left"] * 4 + [None] * 4 + ["right"] * 4, reps=2)
    knees += [{"t_ms": knees[-1]["t_ms"] + 60 * (i + 1), "landmarks": _legs(None)} for i in range(4)]
    assert run_frames("high_knees", knees)["reps"] == 4
    press = lambda up: {**_arms(False), "left_wrist": {"x": .45, "y": .30 - up, "visibility": 1}, "right_wrist": {"x": .55, "y": .30 - up, "visibility": 1}}
    assert run_frames("shoulder_press", _frames(press, [0.0] * 4 + [0.25] * 4 + [0.0] * 4))["reps"] == 3


def test_every_exercise_has_steps_and_real_cue_lists():
    for ex in CATALOG.values():
        d = ex.to_dict()
        assert d["steps"], ex.id
        assert all(len(c) > 3 for c in d["cues"]), ex.id          # not split into letters
        if ex.tracking:
            assert ex.tracking in SPEC, ex.id
