"""Recommendation port.

``recommend`` tries an external model when ``EXERCISE_RECOMMENDER_URL`` is set.
Any failure, timeout, or invalid payload falls back to transparent rules.
Local safety flags are never cleared by a remote model: a concerning health
indicator forces ``requires_human_review``.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.exercise import CONTRACT_VERSION, DISCLAIMER
from app.exercise.programs import personalize

RULES_SOURCE = "rules:exercise-recommender-1.0.0"


def health_review_reasons(ctx: dict) -> list[str]:
    reasons = []
    fatigue = ctx.get("fatigue_score")
    sleep = ctx.get("sleep_duration_h")
    spo2 = ctx.get("oxygen_saturation")
    if fatigue is not None and fatigue >= 6:
        reasons.append("Self-reported fatigue is high (6 or above on the demo scale).")
    if sleep is not None and sleep < 5:
        reasons.append("Last recorded sleep is under 5 hours.")
    if spo2 is not None and spo2 < 92:
        reasons.append("Oxygen saturation is under 92%.")
    if ctx.get("open_warning_count"):
        reasons.append("There is an open health warning for this astronaut.")
    return reasons


def _recovery_items() -> list[dict]:
    from app.exercise.catalog import CATALOG
    rows = []
    for eid in ("shoulder_circles", "heel_slide", "bird_dog"):
        ex = CATALOG[eid]
        rows.append({
            "exercise_id": ex.id, "name": ex.name, "category": ex.category,
            "sets": 2, "reps": ex.default_reps, "duration_s": ex.default_duration_s,
            "rest_s": ex.default_rest_s, "intensity": "easy",
            "reason": "Light example only, because a health indicator needs a person to review it.",
        })
    return rows


def _block_for_today(program: dict, weekday: int) -> list[dict]:
    blocks = program.get("blocks") or []
    match = next((b for b in blocks if b.get("weekday") == weekday), None)
    if match is None and blocks:
        match = blocks[weekday % len(blocks)]
    if not match:
        return []
    items = []
    for item in match["items"]:
        items.append({**item, "reason": f"Scheduled on the example program for this weekday ({match.get('focus')})."})
    return items


def rules_recommendation(profile: dict, ctx: dict, adherence_pct: float | None, weekday: int) -> dict[str, Any]:
    review = health_review_reasons(ctx)
    program = personalize(profile)
    review.extend(program.get("review_reasons") or [])
    # de-dupe
    deduped = []
    for r in review:
        if r not in deduped:
            deduped.append(r)
    present = [k for k in ("fatigue_score", "sleep_duration_h", "resting_heart_rate", "oxygen_saturation",
                           "exercise_minutes_latest", "heart_rate_variability") if ctx.get(k) is not None]
    confidence = round(0.45 + 0.08 * len(present), 2)
    if deduped:
        confidence = min(confidence, 0.5)
        items = _recovery_items()
        reason = "Suggesting a short, easy example session because at least one health or profile flag needs human review. This does not clear anyone to exercise."
    else:
        if adherence_pct is not None and adherence_pct < 50:
            reason = "Recent example-program adherence is under half, so today's suggestion is the scheduled session at the program's written volume, not a harder one."
        else:
            reason = "Today's suggestion follows the personalized example program. No review flag was raised from the available health context."
        items = _block_for_today(program, weekday)
        if adherence_pct is not None and adherence_pct < 50:
            for item in items:
                if item.get("sets") and item["sets"] > 2:
                    item["sets"] = 2
                item["reason"] = "Volume left at a shorter example because recent adherence is low."
    return {
        "contract_version": CONTRACT_VERSION,
        "astronaut_id": profile.get("astronaut_id"),
        "source": RULES_SOURCE,
        "model": None,
        "confidence": confidence,
        "requires_human_review": bool(deduped),
        "review_reasons": deduped,
        "reason": reason,
        "items": items,
        "program_id": program["id"],
        "fallback": None,
        "example_only": True,
        "disclaimer": DISCLAIMER,
    }


def _valid_remote(data: Any) -> bool:
    return isinstance(data, dict) and data.get("contract_version") == CONTRACT_VERSION and isinstance(data.get("items"), list) and data.get("source")


def apply_safety(remote: dict, local_reasons: list[str]) -> dict:
    """Force human review when local health flags exist, even if the model disagrees."""
    reasons = []
    for r in [*local_reasons, *(remote.get("review_reasons") or [])]:
        if r not in reasons:
            reasons.append(r)
    remote = dict(remote)
    remote["review_reasons"] = reasons
    remote["requires_human_review"] = bool(remote.get("requires_human_review")) or bool(local_reasons)
    remote["disclaimer"] = DISCLAIMER
    remote["example_only"] = True
    remote["contract_version"] = CONTRACT_VERSION
    if local_reasons:
        remote["safety_note"] = "Local health flags require human review. A remote model cannot clear them."
    return remote


def call_recommender(url: str, token: str, payload: dict, timeout_s: float = 2.5) -> dict | None:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = httpx.post(url, json=payload, headers=headers, timeout=timeout_s)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not _valid_remote(data):
        return None
    return data


def recommend(profile: dict, ctx: dict, adherence_pct: float | None, weekday: int, *,
              recommender_url: str = "", recommender_token: str = "") -> dict[str, Any]:
    rules = rules_recommendation(profile, ctx, adherence_pct, weekday)
    if not recommender_url:
        return rules
    payload = {
        "contract_version": CONTRACT_VERSION,
        "astronaut_id": profile.get("astronaut_id"),
        "profile": {k: profile.get(k) for k in ("fitness_level", "focus", "limitations", "equipment", "mission_phase")},
        "health_context": ctx,
        "adherence_pct": adherence_pct,
        "weekday": weekday,
    }
    remote = call_recommender(recommender_url, recommender_token, payload)
    if remote is None:
        rules["fallback"] = "rules"
        rules["reason"] = rules["reason"] + " The configured recommendation model was unavailable, so the rules engine answered."
        return rules
    merged = apply_safety(remote, health_review_reasons(ctx))
    merged.setdefault("astronaut_id", profile.get("astronaut_id"))
    merged.setdefault("reason", "Returned by the configured recommendation model.")
    merged.setdefault("confidence", None)
    merged.setdefault("model", None)
    merged["fallback"] = None
    return merged
