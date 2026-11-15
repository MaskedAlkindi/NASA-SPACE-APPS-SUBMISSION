"""LLM providers for the assistant: OpenAI (cloud) and Ollama (local models).

Each provider exposes the same small interface so the assistant can switch at
runtime. The deterministic offline explainer is the implicit third option and
needs no provider.
"""
from __future__ import annotations

import logging
import time

import httpx

from app.core.config import get_settings

log = logging.getLogger("hmt.providers")
REASONING_PREFIXES = ("gpt-5", "o1", "o3", "o4")
EMBEDDING_HINTS = ("embed", "bert", "minilm")


class ProviderError(Exception):
    pass


class OpenAIProvider:
    id = "openai"
    label = "OpenAI (cloud)"
    local = False

    def __init__(self):
        self.s = get_settings()

    def available(self) -> tuple[bool, str]:
        return (True, "API key configured") if self.s.openai_enabled else (False, "OPENAI_API_KEY not set")

    def models(self) -> list[str]:
        opts = [m.strip() for m in self.s.openai_model_options.split(",") if m.strip()]
        return list(dict.fromkeys([self.s.openai_model, *opts]))

    def default_model(self) -> str:
        return self.s.openai_model

    def chat(self, messages: list[dict], model: str) -> tuple[str, dict]:
        from openai import BadRequestError, OpenAI

        client = OpenAI(api_key=self.s.openai_api_key, timeout=self.s.openai_timeout_s, max_retries=1)
        kwargs = {"model": model, "messages": messages, "max_completion_tokens": self.s.openai_max_output_tokens}
        if self.s.openai_reasoning_effort and model.startswith(REASONING_PREFIXES):
            kwargs["reasoning_effort"] = self.s.openai_reasoning_effort
        try:
            resp = client.chat.completions.create(**kwargs)
        except BadRequestError as e:
            if "reasoning_effort" in kwargs and "reasoning" in str(e).lower():
                kwargs.pop("reasoning_effort")
                resp = client.chat.completions.create(**kwargs)
            else:
                raise
        text = (resp.choices[0].message.content or "").strip()
        return text, {"prompt_tokens": getattr(resp.usage, "prompt_tokens", 0) or 0,
                      "completion_tokens": getattr(resp.usage, "completion_tokens", 0) or 0}


class OllamaProvider:
    """Local models served by Ollama (https://ollama.com) - no data leaves the machine."""
    id = "ollama"
    label = "Ollama (local)"
    local = True
    _cache: tuple[float, list[str], str] | None = None   # (time, models, status)

    def __init__(self):
        self.s = get_settings()
        self.base = self.s.ollama_base_url.rstrip("/")

    def _list(self) -> tuple[list[str], str]:
        now = time.monotonic()
        c = OllamaProvider._cache
        if c and now - c[0] < 15:
            return c[1], c[2]
        try:
            r = httpx.get(f"{self.base}/api/tags", timeout=3)
            r.raise_for_status()
            names = []
            for m in r.json().get("models", []):
                name = m.get("name", "")
                fam = " ".join(m.get("details", {}).get("families") or []).lower()
                if any(h in name.lower() or h in fam for h in EMBEDDING_HINTS):
                    continue   # embedding-only models cannot chat
                names.append(name)
            status = f"{len(names)} chat model(s) at {self.base}" if names else f"no chat models installed at {self.base}"
        except Exception as e:
            names, status = [], f"not reachable at {self.base} ({type(e).__name__})"
        OllamaProvider._cache = (now, names, status)
        return names, status

    def available(self) -> tuple[bool, str]:
        names, status = self._list()
        return bool(names), status

    def models(self) -> list[str]:
        return self._list()[0]

    def default_model(self) -> str:
        names = self.models()
        if self.s.ollama_model and self.s.ollama_model in names:
            return self.s.ollama_model
        return names[0] if names else self.s.ollama_model

    def chat(self, messages: list[dict], model: str) -> tuple[str, dict]:
        body = {"model": model, "messages": messages, "stream": False, "keep_alive": "15m",
                "options": {"num_predict": self.s.openai_max_output_tokens, "num_ctx": self.s.ollama_num_ctx,
                            "temperature": 0.2}}
        try:
            r = httpx.post(f"{self.base}/api/chat", json=body, timeout=self.s.ollama_timeout_s)
        except httpx.HTTPError as e:
            raise ProviderError(f"Ollama unreachable: {e}") from e
        if r.status_code >= 400:
            raise ProviderError(f"Ollama HTTP {r.status_code}: {r.text[:200]}")
        j = r.json()
        return (j.get("message", {}).get("content") or "").strip(), {
            "prompt_tokens": int(j.get("prompt_eval_count") or 0), "completion_tokens": int(j.get("eval_count") or 0)}


PROVIDERS = {"openai": OpenAIProvider, "ollama": OllamaProvider}


def get_provider(pid: str):
    cls = PROVIDERS.get(pid)
    if cls is None:
        raise ProviderError(f"unknown provider {pid}")
    return cls()


def catalog() -> list[dict]:
    out = []
    for pid, cls in PROVIDERS.items():
        p = cls()
        ok, detail = p.available()
        out.append({"id": pid, "label": p.label, "local": p.local, "available": ok, "detail": detail,
                    "models": p.models() if ok else [], "default_model": p.default_model() if ok else None})
    out.append({"id": "offline", "label": "Offline explainer (deterministic)", "local": True, "available": True,
                "detail": "Template-based, no LLM", "models": ["deterministic-fallback-1.0"],
                "default_model": "deterministic-fallback-1.0"})
    return out
