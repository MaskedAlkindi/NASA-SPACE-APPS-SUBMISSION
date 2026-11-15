"""Deterministic, offline explanation generator (used when OpenAI is unavailable).

It only restates values present in the structured context, so it cannot invent
measurements. Wording is templated and intentionally conservative.
"""
from __future__ import annotations

ESCALATION = ("**If you have chest pain, fainting, trouble breathing, confusion or a severe headache, "
              "contact the flight surgeon / crew medical officer now.**")
DISCLAIMER = "_HEALTH-01 is a research decision-support prototype, not a medical device or a doctor._"

STATUS_WORDS = {"within_usual_range": "within your usual range", "above_usual_range": "above your usual range",
                "below_usual_range": "below your usual range"}


def _fmt(v, unit):
    if v is None:
        return "n/a"
    if isinstance(v, float) and abs(v) >= 100:
        v = round(v)
    return f"{v:g} {unit}".strip() if isinstance(v, (int, float)) else f"{v} {unit}"


def _metric_lines(dom: dict) -> list[str]:
    lines = []
    for m in dom.get("metrics", []):
        lines.append(f"- {m['label']}: latest {_fmt(m.get('latest'), m['unit'])} "
                     f"(7-day avg {_fmt(m.get('avg_7d'), m['unit'])}, usual ~{_fmt(m.get('baseline_median'), m['unit'])}) — "
                     f"{STATUS_WORDS.get(m['status'], m['status'])}.")
    return lines


def answer(ctx: dict, question: str) -> str:
    intents = ctx["intents"]
    out: list[str] = []
    who = ctx["astronaut_callsign"]
    out.append(f"**Summary for {who}** (data up to {ctx['as_of'] or 'n/a'}; data type: {', '.join(ctx['data_classes_recent']) or 'n/a'})")

    if ctx.get("severe_symptoms_mentioned"):
        out.append(ESCALATION)

    # Observations
    obs = ctx["observations"]
    focus = [d for d in ("cardiovascular", "sleep", "activity", "wellbeing") if d in obs]
    if "overview" in intents or len(focus) == 4:
        out.append("\n**What was measured**")
        for d in focus:
            dom = obs[d]
            flagged = [m["label"] for m in dom["metrics"] if m["status"] != "within_usual_range"]
            out.append(f"- {d.title()}: " + (f"outside usual range — {', '.join(flagged)}." if flagged else "within your usual ranges."))
    else:
        out.append("\n**What was measured**")
        for d in focus:
            out += _metric_lines(obs[d])
    if "sleep" in obs:
        s = obs["sleep"]
        if s.get("sleep_debt_7d_h_vs_7_5h") is not None:
            out.append(f"- Sleep debt over 7 nights (vs 7.5 h reference): {s['sleep_debt_7d_h_vs_7_5h']} h.")
        if s.get("circadian_disruption"):
            out.append(f"- Sleep timing has been irregular (±{s['sleep_timing_variability_h']} h), a circadian-disruption indicator.")
    if ctx.get("environment"):
        out.append("\n**Cabin environment (last 24 h)**")
        for e in ctx["environment"]:
            out.append(f"- {e['label']}: latest {_fmt(e['latest'], e['unit'])}, 24 h max {_fmt(e['max_24h'], e['unit'])}.")
    if ctx["unavailable_metrics"] and ("overview" in intents):
        out.append(f"- Not available: {', '.join(ctx['unavailable_metrics'][:6])}.")

    # Alerts
    if ctx["active_alerts"]:
        out.append("\n**Recent alerts**")
        for a in ctx["active_alerts"][:4]:
            out.append(f"- [{a['severity'].upper()}] {a['title']} ({a['observed']}, {a['source']}): {a['message']}")
    elif "alert" in intents:
        out.append("\nThere are no alerts in the last 3 days.")

    # Predictions
    mo = ctx["model_outputs"]
    if mo:
        out.append("\n**What the models estimate** (prototype models trained on simulated data — estimates, not measurements)")
        an = mo.get("anomaly_detection")
        if an:
            if an["flagged_unusual"]:
                parts = [f"{c['label'].lower()} {c['value']} vs usual {c['baseline_median']}" for c in an["top_contributors"]]
                out.append(f"- Anomaly check: today looks unusual for you, mainly {', '.join(parts)}.")
            else:
                out.append("- Anomaly check: no unusual combination of measurements detected.")
        fe = mo.get("fatigue_estimate")
        if fe:
            out.append(f"- Estimated fatigue: {fe['value_1_to_7']}/7 ({fe['category']}), likely range {fe['range_80pct'][0]}–{fe['range_80pct'][1]}.")
        for f in mo.get("7_day_forecasts", []):
            dom = "sleep" if f["metric"].startswith("sleep") else "cardiovascular"
            if "overview" in intents or "next" in intents or dom in intents:
                out.append(f"- 7-day trend for {f['metric'].replace('_', ' ')}: {f['trend']} "
                           f"(now ~{f['recent_7d_mean']}, day-7 estimate {f['day7_forecast']}, range {f['day7_range_80pct'][0]}–{f['day7_range_80pct'][1]}).")

    # Research
    if ctx["research"] and ("research" in intents or ctx["active_alerts"] or "cardiovascular" in intents or "sleep" in intents):
        out.append("\n**Research context** (NASA documents and published studies)")
        for r in ctx["research"][:3]:
            out.append(f"- [{r['ref']}] {r['title']}: {r['text'][:260]}{'…' if len(r['text']) > 260 else ''} ({r['source']})")

    # Next steps
    out.append("\n**What you could check next**")
    steps = []
    if any(a["severity"] == "warning" for a in ctx["active_alerts"]):
        steps.append("A warning-level alert is active — please discuss it with the flight surgeon / crew medical officer.")
    if "sleep" in obs and any(m["status"] == "below_usual_range" for m in obs["sleep"]["metrics"] if m["label"].startswith("Sleep duration")):
        steps.append("Protect your next sleep period if operations allow.")
    if mo.get("fatigue_estimate") and mo["fatigue_estimate"]["value_1_to_7"] >= 4.5:
        steps.append("Complete a fatigue check-in so the estimate can be confirmed by your own report.")
    if mo.get("anomaly_detection", {}).get("flagged_unusual"):
        steps.append("Repeat the flagged measurements at rest tomorrow morning to see if the change persists.")
    if not steps:
        steps.append("Keep your usual check-ins and wearable routine; nothing currently stands out.")
    out += [f"- {s}" for s in steps]
    out.append("\n" + ESCALATION if not ctx.get("severe_symptoms_mentioned") and ctx["active_alerts"] else "")
    out.append(DISCLAIMER)
    return "\n".join(line for line in out if line is not None)
