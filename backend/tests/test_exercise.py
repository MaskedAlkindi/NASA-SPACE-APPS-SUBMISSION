"""Exercise counters, goals, programs, and API isolation."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.exercise.catalog import CATALOG
from app.exercise.goals import completion_pct, evaluate_goals, missed_dates, period_bounds, streak_days, weekly_adherence
from app.exercise.inference_api import InferenceError, handle_frame, handle_landmarks
from app.exercise.programs import PROGRAMS, personalize
from app.exercise.recommendations import apply_safety, health_review_reasons, recommend, rules_recommendation
from app.exercise.strategy import choose_strategy
from app.exercise.tracking import SPEC, angle_deg, run_frames


def _pt(x, y, visibility=1):
    return {"x": x, "y": y, "visibility": visibility}


def _knee_pose(angle, x=0.5):
    import math
    knee = _pt(x, 0.65)
    hip = _pt(x, 0.40)
    bend = math.radians(180 - angle)
    ankle = _pt(x + math.sin(bend) * 0.22, 0.65 + math.cos(bend) * 0.22)
    return hip, knee, ankle


def squat_pose(angle, visibility=1):
    lm = {}
    for side, x in (("left", 0.42), ("right", 0.58)):
        hip, knee, ankle = _knee_pose(angle, x)
        for name, pt in (("hip", hip), ("knee", knee), ("ankle", ankle)):
            pt = dict(pt)
            pt["visibility"] = visibility
            lm[f"{side}_{name}"] = pt
    return lm


def lunge_pose(bent, straight=170):
    lm = {}
    for side, angle, x in (("left", bent, 0.42), ("right", straight, 0.58)):
        hip, knee, ankle = _knee_pose(angle, x)
        lm[f"{side}_hip"] = hip
        lm[f"{side}_knee"] = knee
        lm[f"{side}_ankle"] = ankle
    return lm


def arm_pose(elevation):
    lm = {}
    for side, x in (("left", 0.40), ("right", 0.62)):
        lm[f"{side}_shoulder"] = _pt(x, 0.45)
        lm[f"{side}_wrist"] = _pt(x, 0.45 - elevation)
    return lm


def _cycle(pose_at, angles, step=100):
    frames = []
    t = 0
    for angle, hold in angles:
        for _ in range(hold):
            frames.append({"t_ms": t, "landmarks": pose_at(angle)})
            t += step
    return frames


def test_knee_geometry_matches_requested_angle():
    hip, knee, ankle = _knee_pose(90, 0.4)
    assert angle_deg(hip, knee, ankle) == pytest.approx(90, abs=0.2)
    hip, knee, ankle = _knee_pose(170, 0.4)
    assert angle_deg(hip, knee, ankle) == pytest.approx(170, abs=0.2)


def test_squat_counts_three_reps_and_ignores_a_shallow_attempt():
    deep = [(170, 3), (100, 4), (170, 5)]
    shallow = [(170, 2), (130, 4), (170, 4)]
    frames = _cycle(squat_pose, deep * 3 + shallow)
    snap = run_frames("squat", frames)
    assert snap["reps"] == 3
    assert any("Partial depth" in flag for flag in snap["form_flags"])


def test_flicker_does_not_count_a_rep():
    frames = [
        {"t_ms": 0, "landmarks": squat_pose(170)},
        {"t_ms": 40, "landmarks": squat_pose(90)},
        {"t_ms": 80, "landmarks": squat_pose(170)},
        {"t_ms": 400, "landmarks": squat_pose(170)},
    ]
    assert run_frames("squat", frames)["reps"] == 0


def test_low_visibility_is_not_a_rep():
    frames = _cycle(lambda a: squat_pose(a, visibility=0.1), [(170, 2), (90, 4), (170, 4)])
    snap = run_frames("squat", frames)
    assert snap["reps"] == 0
    assert snap["status"] == "tracking_lost"


def test_lunge_and_arm_raise_count():
    lunges = _cycle(lambda a: lunge_pose(a if a < 160 else 170, 170 if a < 160 else 170), [(170, 3), (90, 4), (170, 5)] * 2)
    assert run_frames("forward_lunge", lunges)["reps"] == 2
    arms = _cycle(arm_pose, [(0.0, 3), (0.2, 4), (0.0, 5)] * 2)
    assert run_frames("arm_raise", arms)["reps"] == 2


def test_rest_closes_a_set():
    frames = _cycle(squat_pose, [(170, 3), (100, 4), (170, 5)])
    last = frames[-1]["t_ms"]
    frames.append({"t_ms": last + SPEC["squat"]["rest_set_ms"], "landmarks": squat_pose(170)})
    snap = run_frames("squat", frames)
    assert snap["reps"] == 1
    assert snap["completed_sets"] == 1
    assert snap["reps_in_set"] == 0


def test_unknown_exercise_and_catalog_integrity():
    with pytest.raises(ValueError):
        run_frames("handstand", [])
    for ex in CATALOG.values():
        assert ex.example_only if hasattr(ex, "example_only") else True
        assert ex.category in {"strength", "cardio", "mobility", "rehab"}
        if ex.tracking:
            assert ex.tracking in SPEC
    for program in PROGRAMS.values():
        assert program["example_only"] is True
        ids = [item["exercise_id"] for block in program["blocks"] for item in block["items"]]
        assert ids and set(ids) <= set(CATALOG)


def test_personalized_program_swaps_knee_loads_and_scales_sets():
    program = personalize({"astronaut_id": "AST-001", "fitness_level": "beginner", "focus": "strength",
                           "limitations": "left knee soreness", "equipment": ["bodyweight"]})
    ids = [item["exercise_id"] for block in program["blocks"] for item in block["items"]]
    assert "squat" not in ids and "forward_lunge" not in ids
    assert program["requires_human_review"] is True
    assert all(item["sets"] == 2 for item in program["blocks"][0]["items"] if item["reps"])


def test_goal_math_streak_and_missed_days():
    today = date(2026, 11, 14)  # Saturday
    assert period_bounds("week", today) == (date(2026, 11, 9), date(2026, 11, 15))
    sessions = [
        {"date": today, "minutes": 30, "status": "completed"},
        {"date": today - timedelta(days=1), "minutes": 40, "status": "completed"},
        {"date": today - timedelta(days=2), "minutes": 20, "status": "abandoned"},
    ]
    goals = evaluate_goals(sessions, [
        {"period": "day", "metric": "minutes", "target": 60, "label": "Daily"},
        {"period": "week", "metric": "sessions", "target": 4, "label": "Weekly"},
    ], today)
    assert goals[0]["pct"] == 50
    assert goals[1]["actual"] == 2
    assert completion_pct(1, 0) == 0
    assert streak_days([today, today - timedelta(days=1), today - timedelta(days=2)], today) == 3
    assert streak_days([today - timedelta(days=3)], today) == 0
    missed = missed_dates([today - timedelta(days=1)], {0, 1, 2, 3, 4, 5}, today - timedelta(days=3), today, today)
    assert (today - timedelta(days=2)).isoformat() in missed
    assert today.isoformat() not in missed
    weeks = weekly_adherence([today], 6, today, weeks=2)
    assert len(weeks) == 2 and weeks[-1]["sessions"] == 1


def test_strategy_permission_local_and_remote_failures():
    denied = choose_strategy(camera_permission="denied", local_pose="ready", remote_configured=True, remote_consent=True, remote_status="ready")
    assert denied["strategy"] == "manual"
    local = choose_strategy(camera_permission="granted", local_pose="ready", remote_configured=True, remote_consent=False, remote_status="skipped")
    assert local["strategy"] == "local"
    remote = choose_strategy(camera_permission="granted", local_pose="failed", remote_configured=True, remote_consent=True, remote_status="ready")
    assert remote["strategy"] == "remote"
    fallback = choose_strategy(camera_permission="granted", local_pose="failed", remote_configured=True, remote_consent=True, remote_status="failed")
    assert fallback["strategy"] == "manual"
    no_consent = choose_strategy(camera_permission="granted", local_pose="failed", remote_configured=True, remote_consent=False, remote_status="skipped")
    assert no_consent["strategy"] == "manual"


def test_frame_endpoint_requires_consent_and_runtime():
    with pytest.raises(InferenceError) as denied:
        handle_frame({"consent": "landmarks_only", "exercise_id": "squat", "image_base64": "aGk="}, allow_frames=True)
    assert denied.value.status == 403
    with pytest.raises(InferenceError) as disabled:
        handle_frame({"consent": "explicit_frame_upload", "exercise_id": "squat", "image_base64": "aGk="}, allow_frames=False)
    assert disabled.value.status == 403
    with pytest.raises(InferenceError) as missing:
        handle_frame({"consent": "explicit_frame_upload", "exercise_id": "squat", "image_base64": "aGk="}, allow_frames=True)
    assert missing.value.status == 503


def test_landmark_service_counts_and_rejects_missing_consent():
    with pytest.raises(InferenceError):
        handle_landmarks({"exercise_id": "squat", "frames": [{"t_ms": 0, "landmarks": squat_pose(170)}]})
    frames = _cycle(squat_pose, [(170, 3), (100, 4), (170, 5)])
    out = handle_landmarks({"consent": "landmarks_only", "exercise_id": "squat", "frames": frames})
    assert out["snapshot"]["reps"] == 1
    assert out["stored_video"] is False
    continued = [{"t_ms": fr["t_ms"] + 20000, "landmarks": fr["landmarks"]} for fr in frames]
    again = handle_landmarks({"consent": "landmarks_only", "exercise_id": "squat", "frames": continued, "state": out["state"]})
    assert again["snapshot"]["reps"] == 2


def test_rules_flag_fatigue_and_remote_cannot_clear_it():
    profile = {"astronaut_id": "AST-009", "fitness_level": "intermediate", "focus": "strength",
               "limitations": "", "equipment": ["bodyweight", "bands"]}
    flagged = rules_recommendation(profile, {"fatigue_score": 7, "sleep_duration_h": 4}, 90, 0)
    assert flagged["requires_human_review"] is True
    assert flagged["source"].startswith("rules:")
    assert flagged["confidence"] is not None
    assert flagged["reason"]
    assert all(item["intensity"] == "easy" for item in flagged["items"])
    remote = {"contract_version": "1.0.0", "source": "model:test", "model": "test-1", "items": [{"exercise_id": "squat"}],
              "requires_human_review": False, "confidence": 0.99}
    merged = apply_safety(remote, health_review_reasons({"fatigue_score": 7}))
    assert merged["requires_human_review"] is True
    quiet = recommend(profile, {"sleep_duration_h": 7.5, "fatigue_score": 2, "resting_heart_rate": 55}, 80, 0)
    assert quiet["requires_human_review"] is False
    assert quiet["items"]


def test_recommender_timeout_falls_back(monkeypatch):
    monkeypatch.setattr("app.exercise.recommendations.call_recommender", lambda *a, **k: None)
    result = recommend({"astronaut_id": "AST-001", "fitness_level": "intermediate", "focus": "balanced",
                        "limitations": "", "equipment": ["bodyweight"]}, {"sleep_duration_h": 7}, 70, 1,
                       recommender_url="http://127.0.0.1:9/recommend")
    assert result["source"].startswith("rules:")
    assert result["fallback"] == "rules"


def test_api_isolation_manual_log_and_inference(client, orion, mc):
    started = datetime.now(timezone.utc) - timedelta(minutes=30)
    payload = {
        "source": "manual", "started_at": started.isoformat(), "ended_at": datetime.now(timezone.utc).isoformat(),
        "exercises": [{"exercise_id": "squat", "sets": [{"reps": 8, "rest_s": 45}]}],
        "perceived_exertion": 6, "heart_rate_avg": 188, "notes": "manual test",
        "client_id": "test-manual-orion-1", "sync_health": True,
    }
    first = client.post("/api/v1/exercise/astronauts/AST-001/sessions", headers=orion, json=payload)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["astronaut_id"] == "AST-001" and body["summary"]["minutes"] >= 1
    second = client.post("/api/v1/exercise/astronauts/AST-001/sessions", headers=orion, json=payload)
    assert second.status_code == 200 and second.json()["id"] == body["id"]
    hidden = client.get("/api/v1/exercise/astronauts/AST-002/sessions", headers=orion)
    assert hidden.status_code == 404
    vega = client.get("/api/v1/exercise/astronauts/AST-002/sessions", headers=mc)
    assert vega.status_code == 200
    assert all(s["client_id"] != "test-manual-orion-1" for s in vega.json()["sessions"])
    meas = client.get("/api/v1/astronauts/AST-001/measurements?metric=exercise_minutes&days=3", headers=orion).json()
    assert any(item["source_module"] == "exercise" for item in meas["items"])
    alerts = client.get("/api/v1/astronauts/AST-001/alerts", headers=orion).json()["alerts"]
    assert any(a["category"] == "exercise" and a["source"] == "rule:exercise-review" for a in alerts)
    progress = client.get("/api/v1/exercise/astronauts/AST-001/progress", headers=orion)
    assert progress.status_code == 200
    assert "streak_days" in progress.json() and progress.json()["goals"]
    rec = client.get("/api/v1/exercise/astronauts/AST-001/recommendations", headers=orion).json()
    assert rec["contract_version"] == "1.0.0" and rec["reason"] and "confidence" in rec and rec["source"]
    summary = client.get("/api/v1/exercise/astronauts/AST-001/summary", headers=orion).json()
    assert summary["contract_version"] == "1.0.0" and summary["sessions_7d"] >= 1
    ctx = client.get("/api/v1/exercise/astronauts/AST-001/health-context", headers=orion).json()
    assert ctx["contract_version"] == "1.0.0" and "fatigue_score" in ctx
    blocked = client.post("/api/v1/exercise/inference/frame", headers=orion, json={
        "consent": "no", "exercise_id": "squat", "image_base64": "aGk="})
    assert blocked.status_code == 403
    missing = client.post("/api/v1/exercise/inference/frame", headers=orion, json={
        "consent": "explicit_frame_upload", "exercise_id": "squat", "image_base64": "aGk="})
    assert missing.status_code == 403  # remote frames disabled unless configured
    counted = client.post("/api/v1/exercise/inference/landmarks", headers=orion, json={
        "consent": "landmarks_only", "exercise_id": "arm_raise",
        "frames": _cycle(arm_pose, [(0.0, 3), (0.2, 4), (0.0, 5)]),
    })
    assert counted.status_code == 200, counted.text
    assert counted.json()["snapshot"]["reps"] == 1
    catalog = client.get("/api/v1/exercise/catalog", headers=orion).json()
    assert catalog["example_only"] is True and any(e["tracking"] == "squat" for e in catalog["exercises"])
    mods = {m["id"]: m for m in client.get("/api/v1/modules", headers=orion).json()["modules"]}
    assert mods["exercise"]["status"]["state"] in {"available", "connected", "waiting"}
