from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

TIMEOUT = httpx.Timeout(12.0, connect=6.0)
USER_AGENT = "HEALTH-01-server-connector/1.0"


@dataclass
class Result:
    ok: bool
    message: str
    data: dict = field(default_factory=dict)       # small JSON summary shown in the UI
    measurements: list[dict] = field(default_factory=list)   # optional NormalizedMeasurement-style records


class Connector:
    """Subclass and set id/name/description. Override check()."""
    id: str = ""
    name: str = ""
    description: str = ""
    default_url: str = ""
    url_hint: str = "https://…"
    # Allow URLs on private networks (a local Ollama or a crew server on the LAN). Public-data connectors say False.
    allow_private: bool = True

    def check(self, url: str, settings: dict) -> Result:
        raise NotImplementedError

    # helpers
    def get_json(self, url: str, headers: dict | None = None):
        validate_url(url, self.allow_private)
        with httpx.Client(timeout=TIMEOUT, follow_redirects=False, headers={"User-Agent": USER_AGENT, **(headers or {})}) as c:
            r = c.get(url)
            r.raise_for_status()
            return r.json()

    def describe(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description,
                "default_url": self.default_url, "url_hint": self.url_hint}


def validate_url(url: str, allow_private: bool) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ValueError("URL must start with http:// or https://")
    if allow_private:
        return
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except socket.gaierror as e:
        raise ValueError(f"cannot resolve {p.hostname}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise ValueError("this connector only talks to public internet addresses")
