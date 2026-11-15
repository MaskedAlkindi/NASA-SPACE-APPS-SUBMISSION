"""Finds every Connector subclass in servers/connectors/*.py."""
from __future__ import annotations

import importlib
import inspect
import pkgutil

from servers import connectors as pkg
from servers.base import Connector


def all_connectors() -> dict[str, Connector]:
    found: dict[str, Connector] = {}
    for info in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"{pkg.__name__}.{info.name}")
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, Connector) and obj is not Connector and obj.id and obj.id not in found:
                found[obj.id] = obj()
    return found


def run_check(kind: str, url: str, settings: dict | None = None):
    c = all_connectors().get(kind)
    if c is None:
        raise KeyError(kind)
    return c.check(url, settings or {})
