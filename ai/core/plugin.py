"""Base class for model plug-ins.

A plug-in folder contains manifest.json + the Python class named by `entrypoint`
(+ optional artifacts/ and report.json). Subclasses implement `_load` and `_predict`.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from ai.core.data import HealthDataView, check_inputs
from ai.core.types import Assessment, ModelManifest


class ModelPlugin:
    manifest: ModelManifest
    folder: Path

    def __init__(self, manifest: ModelManifest, folder: Path):
        self.manifest = manifest
        self.folder = folder
        self._loaded = False
        self._lock = threading.Lock()
        self.last_error: str | None = None

    # ---------------- lifecycle
    @property
    def loaded(self) -> bool:
        return self._loaded

    def load(self) -> None:
        with self._lock:
            if not self._loaded:
                self._load()
                self._loaded = True

    def unload(self) -> None:
        with self._lock:
            self._unload()
            self._loaded = False

    def _load(self) -> None:          # override: read artifacts
        pass

    def _unload(self) -> None:        # override: free memory
        pass

    def artifact_path(self) -> Path | None:
        return self.folder / self.manifest.artifact if self.manifest.artifact else None

    def report(self) -> dict | None:
        p = self.folder / (self.manifest.report or "report.json")
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

    def health(self) -> dict[str, Any]:
        art = self.artifact_path()
        return {"loaded": self._loaded, "artifact_present": (art.exists() if art else None),
                "last_error": self.last_error, "status": self.manifest.status}

    # ---------------- inference
    def predict(self, view: HealthDataView) -> Assessment:
        m = self.manifest
        q = check_inputs(view, m.inputs, getattr(view, "now", None))   # a view may carry its own clock (replays, tests)
        if not q["ok"]:
            why = "Required inputs unavailable"
            if q["missing"]:
                why += f"; missing: {', '.join(q['missing'])}"
            if q["stale"]:
                why += f"; stale: {', '.join(s['metric'] for s in q['stale'])}"
            if q["unit_mismatch"]:
                why += f"; unit mismatch: {q['unit_mismatch']}"
            return Assessment.unavailable(view.astronaut_id, m, "insufficient_data", why + ".", **q)
        self.load()
        a = self._predict(view, q)
        a.data_quality = {**q, **a.data_quality}
        return a

    def _predict(self, view: HealthDataView, quality: dict) -> Assessment:   # override
        raise NotImplementedError
