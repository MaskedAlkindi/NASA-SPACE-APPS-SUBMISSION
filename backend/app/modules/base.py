"""Module contract shared by every integration.

A module:
  * declares an ID, version, category and the canonical metrics it can produce
  * exposes its (non-secret) configuration
  * converts source-specific payloads into NormalizedMeasurement objects (``ingest``)
  * validates single records (``validate``)
  * reports its own health (``status``)

Modules never import each other. The registry isolates failures, so the system
keeps working when a module cannot load or its upstream source is down.
"""
from __future__ import annotations

from abc import ABC
from typing import Any

from pydantic import ValidationError

from app.schemas.measurement import DataClass, NormalizedMeasurement, Quality


class ModuleError(Exception):
    pass


class HealthModule(ABC):
    module_id: str = "base"
    version: str = "0.0.0"
    name: str = "Base module"
    description: str = ""
    category: str = "device"          # device | research | simulation | environment | questionnaire
    data_class: DataClass = DataClass.real
    supported_metrics: list[str] = []
    accepts_ingest: bool = True

    def __init__(self, config: dict[str, Any] | None = None):
        self.config: dict[str, Any] = {**self.default_config(), **(config or {})}
        self.last_error: str | None = None

    # ---- configuration -------------------------------------------------
    def default_config(self) -> dict[str, Any]:
        return {}

    def public_config(self) -> dict[str, Any]:
        return {k: v for k, v in self.config.items() if "key" not in k.lower() and "secret" not in k.lower()}

    # ---- health ----------------------------------------------------------
    def status(self) -> dict[str, Any]:
        return {"state": "available", "detail": "ready"}

    # ---- ingestion -------------------------------------------------------
    def map_record(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Translate a source-specific record into canonical field names. Override per source."""
        return dict(raw)

    def validate(self, raw: dict[str, Any]) -> NormalizedMeasurement:
        rec = self.map_record(raw)
        rec.setdefault("data_class", self.data_class.value)
        rec["source_module"] = self.module_id
        rec.setdefault("quality", Quality.unknown.value)
        if rec.get("metric") not in self.supported_metrics:
            raise ModuleError(f"{self.module_id} does not support metric '{rec.get('metric')}'")
        try:
            return NormalizedMeasurement(**rec)
        except ValidationError as e:
            msgs = "; ".join(err["msg"] for err in e.errors())
            raise ModuleError(msgs) from None

    def ingest(self, records: list[dict[str, Any]]) -> tuple[list[NormalizedMeasurement], list[str]]:
        ok, errors = [], []
        for i, r in enumerate(records):
            try:
                ok.append(self.validate(r))
            except (ModuleError, ValueError, TypeError) as e:
                errors.append(f"record {i}: {e}")
        return ok, errors

    def describe(self) -> dict[str, Any]:
        return {"id": self.module_id, "version": self.version, "name": self.name,
                "description": self.description, "category": self.category,
                "data_class": self.data_class.value, "supported_metrics": self.supported_metrics,
                "accepts_ingest": self.accepts_ingest, "config": self.public_config()}
