"""Assistant orchestration: context -> (OpenAI | Ollama | offline explainer) -> safety post-processing.

Provider/model selection order: per-request choice -> default saved from the UI
(app_settings) -> ASSISTANT_PROVIDER env ("auto" = OpenAI if keyed, else local
Ollama if reachable, else offline).

Cost controls (OpenAI): configurable cheap model, max output tokens, history
limit, passage limit, timeout, per-user rate limit, global daily budgets.
Local Ollama models share the rate limit but not the paid-API budgets.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.assistant import fallback
from app.assistant.context import build_context
from app.assistant.providers import ProviderError, catalog, get_provider
from app.core.config import get_settings
from app.core.ratelimit import RateLimiter
from app.database.models import AppSetting, AssistantUsage

log = logging.getLogger("hmt.assistant")
_settings = get_settings()
limiter = RateLimiter(_settings.assistant_rate_limit_per_minute, 60)
SETTING_KEY = "assistant"

SYSTEM_PROMPT = """You are the HEALTH-01 health explanation assistant for astronauts who are NOT doctors.
You receive a CONTEXT JSON object built by the HEALTH-01 backend. Follow these rules strictly:
1. Use ONLY facts and numbers present in CONTEXT. Never invent measurements, dates or values. If something is not in CONTEXT, say it is not available.
2. Clearly separate "What was measured" (observations) from "What the models estimate" (model_outputs). Say model outputs are estimates from prototype models trained on simulated data.
3. Explain uncertainty (ranges, missing inputs). Never give a diagnosis; use cautious language ("can be associated with").
4. Do not give medication, dosing or treatment instructions. General self-care (rest, sleep, hydration, re-measuring) and contacting the flight surgeon / crew medical officer are allowed.
5. If any alert has severity "warning", or severe_symptoms_mentioned is true, tell the astronaut to contact the flight surgeon / crew medical officer now.
6. When using a research item, cite it as [R1], [R2] ... and mention its caveat briefly. Research findings describe other people, not this astronaut.
7. Plain language, friendly, concise: at most ~180 words, short bullet points are fine.
8. You are decision support and never replace a medical professional."""


def _today():
    return datetime.now(timezone.utc).date()


# ---------------------------------------------------------------- provider selection
def saved_default(db: Session) -> dict:
    row = db.get(AppSetting, SETTING_KEY)
    return dict(row.value) if row and row.value else {}


def save_default(db: Session, provider: str, model: str | None, username: str) -> dict:
    validate_choice(provider, model)
    row = db.get(AppSetting, SETTING_KEY) or AppSetting(key=SETTING_KEY)
    row.value = {"provider": provider, "model": model}
    row.updated_by = username
    row.updated_at = datetime.now(timezone.utc)
    db.merge(row)
    db.commit()
    return row.value


def validate_choice(provider: str, model: str | None) -> None:
    if provider == "auto":
        return
    entry = next((p for p in catalog() if p["id"] == provider), None)
    if entry is None:
        raise ValueError(f"unknown provider '{provider}'")
    if not entry["available"]:
        raise ValueError(f"provider '{provider}' is not available: {entry['detail']}")
    if model and model not in entry["models"]:
        raise ValueError(f"model '{model}' is not available for {provider}; choose from {entry['models']}")


def resolve(db: Session, provider: str | None = None, model: str | None = None) -> tuple[str, str | None, str]:
    """Return (provider_id, model, how_selected). provider_id may be 'offline'."""
    how = "request"
    if not provider or provider == "default":
        saved = saved_default(db)
        provider, model, how = saved.get("provider"), saved.get("model"), "saved default"
        if not provider:
            provider, model, how = _settings.assistant_provider, None, "environment"
    if provider == "auto":
        for pid in ("openai", "ollama"):
            p = get_provider(pid)
            if p.available()[0]:
                return pid, p.default_model(), f"{how} (auto)"
        return "offline", None, f"{how} (auto)"
    if provider == "offline":
        return "offline", None, how
    p = get_provider(provider)
    return provider, model or p.default_model(), how


def status(db: Session) -> dict:
    pid, model, how = resolve(db)
    return {"active": {"provider": pid, "model": model, "selected_by": how},
            "saved_default": saved_default(db) or None, "env_default": _settings.assistant_provider,
            "providers": catalog()}


# ---------------------------------------------------------------- usage / budgets
def usage_today(db: Session) -> dict:
    row = db.execute(select(func.count(AssistantUsage.id), func.coalesce(func.sum(AssistantUsage.prompt_tokens + AssistantUsage.completion_tokens), 0))
                     .where(AssistantUsage.day == _today(), AssistantUsage.mode == "openai")).one()
    return {"requests": int(row[0]), "tokens": int(row[1])}


def budget_ok(db: Session) -> tuple[bool, str]:
    u = usage_today(db)
    if _settings.assistant_daily_request_budget and u["requests"] >= _settings.assistant_daily_request_budget:
        return False, "daily OpenAI request budget reached"
    if _settings.assistant_daily_token_budget and u["tokens"] >= _settings.assistant_daily_token_budget:
        return False, "daily OpenAI token budget reached"
    return True, ""


def _record(db, username, mode, model="", pt=0, ct=0):
    db.add(AssistantUsage(username=username, day=_today(), mode=mode, model=model or "", prompt_tokens=pt, completion_tokens=ct))
    db.commit()


# Kept as a module-level hook so tests can mock the network call.
def _call_llm(provider: str, model: str, messages: list[dict]) -> tuple[str, dict]:
    return get_provider(provider).chat(messages, model)


def grounding_check(answer: str, ctx: dict) -> list[str]:
    """Flag numbers in the answer that do not appear anywhere in the context (cheap hallucination guard)."""
    ctx_text = json.dumps(ctx)
    ctx_nums = {float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", ctx_text)}
    allowed = {1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 10.0, 24.0, 80.0, 100.0}
    flagged = []
    for n in re.findall(r"(?<![\w\[R])-?\d+(?:\.\d+)?", answer):
        v = float(n)
        if v in allowed or v in ctx_nums or any(abs(v - c) <= max(0.051, abs(c) * 0.01) for c in ctx_nums):
            continue
        flagged.append(n)
    return flagged


def chat(db: Session, username: str, astronaut_id: str, message: str, history: list[dict],
         provider: str | None = None, model: str | None = None) -> dict:
    ctx = build_context(db, astronaut_id, message, _settings.assistant_max_passages)
    citations = [{"ref": r["ref"], "title": r["title"], "source": r["source"], "type": r["type"]} for r in ctx["research"]]
    base = {"context_summary": {"as_of": ctx["as_of"], "intents": ctx["intents"], "alerts": len(ctx["active_alerts"]),
                                "research_passages": len(ctx["research"]), "data_classes": ctx["data_classes_recent"]},
            "citations": citations}
    reason = None
    try:
        pid, mdl, how = resolve(db, provider, model)
    except ProviderError as e:
        pid, mdl, how, reason = "offline", None, "error", str(e)

    if pid == "offline":
        if reason is None:
            reason = ("no LLM provider available (set OPENAI_API_KEY or start Ollama with a chat model)"
                      if "auto" in how else "offline explainer selected")
    else:
        p = get_provider(pid)
        ok, detail = p.available()
        if not ok:
            reason = f"{p.label} unavailable: {detail}"
        elif mdl not in p.models():
            reason = f"model '{mdl}' not available for {p.label}"
        else:
            allowed, wait = limiter.allow(username)
            if not allowed:
                reason = f"rate limit reached; retry in {wait:.0f}s"
            elif pid == "openai":
                okb, why = budget_ok(db)
                if not okb:
                    reason = why
    if reason is None:
        hist = [{"role": h["role"], "content": str(h["content"])[:1500]} for h in history[-_settings.assistant_history_limit:]
                if h.get("role") in ("user", "assistant")]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}, *hist,
                    {"role": "user", "content": f"CONTEXT:\n{json.dumps(ctx, default=str, separators=(',', ':'))}\n\nQUESTION: {message}"}]
        try:
            text, usage = _call_llm(pid, mdl, messages)
            _record(db, username, pid, mdl, usage["prompt_tokens"], usage["completion_tokens"])
            if text:
                flagged = grounding_check(text, ctx)
                if flagged:
                    text += ("\n\n_Note: some figures in this answer could not be matched to your recorded data "
                             f"({', '.join(flagged[:5])}); rely on the dashboard values._")
                if ctx["severe_symptoms_mentioned"] and "flight surgeon" not in text.lower():
                    text = fallback.ESCALATION + "\n\n" + text
                text += "\n\n" + fallback.DISCLAIMER
                return {**base, "answer": text, "mode": pid, "provider": pid, "model": mdl, "selected_by": how,
                        "usage": usage, "grounding_flags": flagged}
            reason = "model returned an empty answer"
        except Exception as e:
            log.warning("%s call failed: %s", pid, e)
            reason = f"{pid} request failed ({type(e).__name__})"
    _record(db, username, "offline")
    return {**base, "answer": fallback.answer(ctx, message), "mode": "offline", "provider": "offline",
            "model": "deterministic-fallback-1.0", "requested": {"provider": pid, "model": mdl},
            "fallback_reason": reason, "usage": None}
