"""Model registry: discovers plug-ins from manifests, keeps enable/disable state, loads lazily.

Discovery: every `manifest.json` under ai/models/ (and any extra folders listed in the
HMT_AI_MODEL_PATHS environment variable, separated by os.pathsep). The core never imports
a model by name - it only follows the `entrypoint` declared in each manifest.
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from ai.core.data import HealthDataView
from ai.core.plugin import ModelPlugin
from ai.core.types import Assessment, ModelManifest
from ai.imported.store import import_dir

log = logging.getLogger("hmt.ai.registry")
MODELS_DIR = Path(__file__).resolve().parents[1] / "models"


class StateStore(Protocol):
    """Persists per-model settings (enabled flag, threshold overrides)."""
    def get(self, model_id: str) -> dict | None: ...
    def set(self, model_id: str, state: dict) -> None: ...


class JsonStateStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _read(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def get(self, model_id):
        return self._read().get(model_id)

    def set(self, model_id, state):
        with self._lock:
            data = self._read()
            data[model_id] = state
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=1), encoding="utf-8")


class MemoryStateStore:
    def __init__(self):
        self.data: dict[str, dict] = {}

    def get(self, model_id):
        return self.data.get(model_id)

    def set(self, model_id, state):
        self.data[model_id] = state


class RegistryEntry:
    def __init__(self, manifest: ModelManifest, folder: Path):
        self.manifest = manifest
        self.folder = folder
        self.plugin: ModelPlugin | None = None
        self.load_error: str | None = None


class ModelRegistry:
    def __init__(self, state: StateStore | None = None, search_paths: list[Path] | None = None, max_workers: int = 4):
        self.state = state or MemoryStateStore()
        extra = [Path(p) for p in os.getenv("HMT_AI_MODEL_PATHS", "").split(os.pathsep) if p]
        self.import_root = import_dir()
        self.search_paths = search_paths or [MODELS_DIR, self.import_root, *extra]
        self.entries: dict[str, RegistryEntry] = {}
        self.invalid: dict[str, str] = {}
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ai-model")
        self.discover()

    # ---------------- discovery
    def discover(self) -> None:
        self.entries.clear()
        self.invalid.clear()
        for root in self.search_paths:
            if not root.exists():
                continue
            for mf in sorted(root.glob("*/manifest.json")):
                try:
                    manifest = ModelManifest(**json.loads(mf.read_text(encoding="utf-8")))
                except (ValidationError, json.JSONDecodeError) as e:
                    self.invalid[str(mf)] = str(e).splitlines()[0]
                    log.warning("invalid manifest %s: %s", mf, e)
                    continue
                if manifest.id in self.entries:
                    self.invalid[str(mf)] = f"duplicate model id {manifest.id}"
                    continue
                self.entries[manifest.id] = RegistryEntry(manifest, mf.parent)
        log.info("AI registry: %d models discovered (%d invalid)", len(self.entries), len(self.invalid))

    # ---------------- state
    def settings(self, model_id: str) -> dict:
        e = self.entries[model_id]
        st = self.state.get(model_id) or {}
        return {"enabled": st.get("enabled", e.manifest.enabled_by_default),
                "thresholds": {**e.manifest.alerting.thresholds, **st.get("thresholds", {})}}

    def set_enabled(self, model_id: str, enabled: bool) -> dict:
        if model_id not in self.entries:
            raise KeyError(model_id)
        st = self.state.get(model_id) or {}
        st["enabled"] = bool(enabled)
        self.state.set(model_id, st)
        if not enabled:
            self.unload(model_id)
        return self.settings(model_id)

    def enabled_ids(self) -> list[str]:
        return [mid for mid in self.entries if self.settings(mid)["enabled"]]

    # ---------------- loading
    def plugin(self, model_id: str) -> ModelPlugin:
        e = self.entries[model_id]
        if e.plugin is None:
            try:
                mod_name, cls_name = e.manifest.entrypoint.split(":")
                if str(e.folder.parent) not in sys.path and e.folder.parent != MODELS_DIR:
                    sys.path.append(str(e.folder.parent))          # external plug-in folders
                cls = getattr(importlib.import_module(mod_name), cls_name)
                if not issubclass(cls, ModelPlugin):
                    raise TypeError(f"{cls_name} must subclass ai.core.plugin.ModelPlugin")
                e.plugin = cls(e.manifest, e.folder)
                e.load_error = None
            except Exception as ex:   # noqa: BLE001 - isolate faulty plug-ins
                e.load_error = f"{type(ex).__name__}: {ex}"
                log.exception("cannot import model %s", model_id)
                raise
        return e.plugin

    def unload(self, model_id: str) -> None:
        e = self.entries.get(model_id)
        if e and e.plugin and e.plugin.loaded:
            e.plugin.unload()

    # ---------------- inference
    def run(self, model_id: str, view: HealthDataView) -> Assessment:
        e = self.entries[model_id]
        m = e.manifest
        if not self.settings(model_id)["enabled"]:
            return Assessment.unavailable(view.astronaut_id, m, "disabled", "Model is disabled.")
        try:
            plugin = self.plugin(model_id)
        except Exception:   # noqa: BLE001
            return Assessment.unavailable(view.astronaut_id, m, "error", f"Model could not be loaded: {e.load_error}")
        try:
            fut = self._pool.submit(plugin.predict, view)
        except RuntimeError:   # interpreter shutting down
            return Assessment.unavailable(view.astronaut_id, m, "error", "Engine is shutting down.")
        try:
            a = fut.result(timeout=m.execution.timeout_s)
            plugin.last_error = None
            return a
        except FutureTimeout:
            plugin.last_error = f"timed out after {m.execution.timeout_s}s"
            return Assessment.unavailable(view.astronaut_id, m, "error", f"Model timed out after {m.execution.timeout_s}s.")
        except Exception as ex:   # noqa: BLE001
            plugin.last_error = f"{type(ex).__name__}: {ex}"
            log.exception("model %s failed", model_id)
            return Assessment.unavailable(view.astronaut_id, m, "error", f"Model failed: {type(ex).__name__}.")

    def run_all(self, view: HealthDataView, model_ids: list[str] | None = None) -> list[Assessment]:
        ids = [i for i in (model_ids or self.enabled_ids()) if i in self.entries]
        return [self.run(i, view) for i in ids]

    # ---------------- description
    def describe(self, model_id: str) -> dict[str, Any]:
        e = self.entries[model_id]
        plugin_health = e.plugin.health() if e.plugin else {"loaded": False}
        report = None
        if e.manifest.report:
            rp = e.folder / e.manifest.report
            if rp.exists():
                report = json.loads(rp.read_text(encoding="utf-8"))
        rules_path = e.folder / "rules.json"
        rules = json.loads(rules_path.read_text(encoding="utf-8")) if rules_path.exists() else None
        return {**e.manifest.model_dump(), **self.settings(model_id), "health": plugin_health,
                "load_error": e.load_error, "report": report, "imported": rules is not None, "rules": rules}

    def describe_all(self) -> list[dict[str, Any]]:
        return [self.describe(i) for i in self.entries]
