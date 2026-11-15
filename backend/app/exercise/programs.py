"""Example programs. Each one is labelled as a demonstration, not a flight protocol.

Public descriptions of ISS countermeasures group exercise into resistance,
aerobic, and mobility work. These programs only borrow that grouping. They are
not ARED, CEVIS, or NASA-STD prescriptions.
"""
from __future__ import annotations

from typing import Any

from app.exercise.catalog import CATALOG

EXAMPLE_NOTE = (
    "Example program for the demo. Not a medically validated prescription and not a NASA flight protocol."
)

KNEE_SWAP = {"squat": "glute_bridge", "forward_lunge": "heel_slide"}
SETS_BY_LEVEL = {"beginner": 2, "intermediate": 3, "advanced": 4}


def _item(exercise_id: str, **overrides: Any) -> dict:
    ex = CATALOG[exercise_id]
    row = {
        "exercise_id": ex.id, "name": ex.name, "category": ex.category,
        "sets": ex.default_sets, "reps": ex.default_reps, "duration_s": ex.default_duration_s,
        "rest_s": ex.default_rest_s, "intensity": ex.intensity, "equipment": list(ex.equipment),
        "tracking": ex.tracking,
    }
    row.update(overrides)
    return row


def _program(pid: str, name: str, kind: str, equipment: list[str], days: list[int],
             blocks: list[dict], summary: str) -> dict:
    return {
        "id": pid, "name": name, "kind": kind, "example_only": True, "disclaimer": EXAMPLE_NOTE,
        "summary": summary, "equipment": equipment,
        "schedule": {"weekdays": days, "sessions_per_week": len(days)},
        "progression": "Example progression only: add a set when the last session felt easy (RPE 6 or below). Do not progress through pain.",
        "blocks": blocks,
    }


def _block(weekday: int, focus: str, items: list[dict]) -> dict:
    return {"weekday": weekday, "focus": focus, "items": items}


GENERAL = _program(
    "example_general_maintenance", "General maintenance (example)", "general",
    ["bodyweight", "bands", "cycle"], [0, 1, 2, 3, 4, 5], [
        _block(0, "strength", [_item("squat"), _item("forward_lunge"), _item("glute_bridge"), _item("band_row")]),
        _block(1, "cardio", [_item("cycle"), _item("arm_raise")]),
        _block(2, "mobility", [_item("hip_flexor_stretch"), _item("thoracic_rotation"), _item("shoulder_circles"), _item("bird_dog")]),
        _block(3, "strength", [_item("squat"), _item("pushup"), _item("calf_raise"), _item("plank")]),
        _block(4, "cardio", [_item("brisk_march"), _item("arm_raise")]),
        _block(5, "mobility", [_item("hip_flexor_stretch"), _item("bird_dog"), _item("heel_slide"), _item("shoulder_circles")]),
    ],
    "Six-day example that mixes strength, aerobic work, and mobility for any crew member.",
)

MISSION = _program(
    "example_mission_long_duration", "Long-duration mission mix (example)", "mission",
    ["bodyweight", "bands", "cycle"], [0, 1, 2, 3, 4, 5], [
        _block(0, "strength", [_item("squat", sets=4), _item("forward_lunge", sets=3), _item("band_row", sets=3)]),
        _block(1, "cardio", [_item("cycle", duration_s=1500)]),
        _block(2, "strength", [_item("pushup"), _item("glute_bridge"), _item("plank")]),
        _block(3, "cardio", [_item("cycle", duration_s=1200), _item("arm_raise")]),
        _block(4, "strength", [_item("squat"), _item("calf_raise"), _item("band_row")]),
        _block(5, "mobility", [_item("hip_flexor_stretch"), _item("thoracic_rotation"), _item("bird_dog")]),
    ],
    "Example mission-phase mix with more resistance and aerobic time. Still only a demo.",
)

STRENGTH = _program(
    "example_strength", "Strength emphasis (example)", "general",
    ["bodyweight", "bands"], [0, 2, 4], [
        _block(0, "strength", [_item("squat", sets=4), _item("forward_lunge"), _item("pushup"), _item("plank")]),
        _block(2, "strength", [_item("glute_bridge"), _item("band_row"), _item("calf_raise"), _item("squat")]),
        _block(4, "strength", [_item("forward_lunge"), _item("pushup"), _item("bird_dog")]),
    ],
    "Example three-day strength emphasis.",
)

CARDIO = _program(
    "example_cardio", "Cardiovascular emphasis (example)", "general",
    ["bodyweight", "cycle"], [0, 1, 3, 4], [
        _block(0, "cardio", [_item("cycle", duration_s=1500), _item("arm_raise")]),
        _block(1, "cardio", [_item("brisk_march", duration_s=900)]),
        _block(3, "cardio", [_item("cycle", duration_s=1200), _item("squat", sets=2)]),
        _block(4, "cardio", [_item("brisk_march"), _item("shoulder_circles")]),
    ],
    "Example aerobic emphasis with a little strength.",
)

MOBILITY = _program(
    "example_mobility", "Mobility and flexibility (example)", "general",
    ["bodyweight"], [0, 1, 2, 3, 4, 5], [
        _block(d, "mobility", [_item("arm_raise"), _item("hip_flexor_stretch"), _item("thoracic_rotation"), _item("shoulder_circles")])
        for d in range(6)
    ],
    "Example daily mobility session. Suitable as a lighter day in the demo.",
)

REHAB = _program(
    "example_rehab_gentle", "Gentle range-of-motion (example)", "rehab",
    ["bodyweight"], [0, 1, 2, 3, 4, 5], [
        _block(d, "rehab", [_item("heel_slide"), _item("glute_bridge", sets=2), _item("bird_dog"), _item("shoulder_circles")])
        for d in range(6)
    ],
    "Example gentle session. It is not rehabilitation care and should be reviewed by a person before use.",
)

PROGRAMS: dict[str, dict] = {p["id"]: p for p in (GENERAL, MISSION, STRENGTH, CARDIO, MOBILITY, REHAB)}


def program_list() -> list[dict]:
    return list(PROGRAMS.values())


def _equipment_ok(item: dict, available: set[str]) -> bool:
    needed = set(item.get("equipment") or ["bodyweight"])
    return needed <= available


def personalize(profile: dict) -> dict:
    """Build a per-astronaut example program from level, focus, equipment, and notes."""
    focus = profile.get("focus") or "balanced"
    level = profile.get("fitness_level") or "intermediate"
    base_id = {
        "strength": STRENGTH["id"], "cardio": CARDIO["id"], "mobility": MOBILITY["id"], "rehab": REHAB["id"],
    }.get(focus, GENERAL["id"])
    base = PROGRAMS[base_id]
    equipment = set(profile.get("equipment") or ["bodyweight"])
    equipment.add("bodyweight")
    limitations = (profile.get("limitations") or "").lower()
    knee = "knee" in limitations
    sets = SETS_BY_LEVEL.get(level, 3)
    review: list[str] = []
    if limitations.strip():
        review.append("The profile includes a limitation note, so a person should review this example before use.")
    if focus == "rehab":
        review.append("Rehab-oriented examples are not therapy and need human review.")
    blocks = []
    for block in base["blocks"]:
        items = []
        for item in block["items"]:
            eid = item["exercise_id"]
            if knee and eid in KNEE_SWAP:
                eid = KNEE_SWAP[eid]
                review.append("Knee is mentioned in the profile, so squats and lunges were swapped for gentler examples.")
            nxt = _item(eid)
            if nxt["reps"]:
                nxt["sets"] = sets
            if not _equipment_ok(nxt, equipment):
                if "cycle" in (nxt.get("equipment") or []):
                    nxt = _item("brisk_march")
                else:
                    continue
            items.append(nxt)
        if items:
            blocks.append({**block, "items": items})
    deduped = []
    for reason in review:
        if reason not in deduped:
            deduped.append(reason)
    aid = profile.get("astronaut_id") or "astronaut"
    return {
        "id": f"personalized:{aid}",
        "name": f"Personalized example ({focus})",
        "kind": "personalized",
        "example_only": True,
        "disclaimer": EXAMPLE_NOTE,
        "summary": f"Built for this astronaut from the {base['name']} template at {level} volume.",
        "based_on": base_id,
        "equipment": sorted(equipment),
        "schedule": base["schedule"],
        "progression": base["progression"],
        "requires_human_review": bool(deduped),
        "review_reasons": deduped,
        "blocks": blocks,
        "fitness_level": level,
        "focus": focus,
    }
