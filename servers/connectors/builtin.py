"""Built-in connectors."""
from __future__ import annotations

from datetime import datetime, timezone

from servers.base import Connector, Result


def _scale_g(kp: float) -> str:
    # NOAA Space Weather Scales: geomagnetic storms G1..G5 at Kp 5..9
    return "none" if kp < 5 else f"G{min(5, int(kp) - 4)}"


def _scale_s(pfu: float) -> str:
    # NOAA Space Weather Scales: solar radiation storms S1..S5 at >=10 MeV proton flux 10, 1e2, 1e3, 1e4, 1e5 pfu
    for level, threshold in ((5, 1e5), (4, 1e4), (3, 1e3), (2, 1e2), (1, 10)):
        if pfu >= threshold:
            return f"S{level}"
    return "none"


class NoaaSpaceWeather(Connector):
    id = "noaa_swpc"
    name = "NOAA space weather"
    description = ("Live planetary Kp index and GOES >=10 MeV proton flux from NOAA's Space Weather Prediction Center, "
                   "mapped to the NOAA G and S storm scales. Context for the radiation hazard; not a dose measurement.")
    default_url = "https://services.swpc.noaa.gov"
    allow_private = False

    def check(self, url: str, settings: dict) -> Result:
        base = url.rstrip("/")
        kp_rows = self.get_json(f"{base}/products/noaa-planetary-k-index.json")
        if kp_rows and isinstance(kp_rows[0], list):          # older format: header row + lists
            head = kp_rows[0]
            kp_rows = [dict(zip(head, r)) for r in kp_rows[1:]]
        last_kp = kp_rows[-1]
        kp = float(last_kp.get("Kp", last_kp.get("kp_index", 0)))
        protons = self.get_json(f"{base}/json/goes/primary/integral-protons-1-day.json")
        p10 = [p for p in protons if p.get("energy") == ">=10 MeV" and p.get("flux") is not None]
        flux = float(p10[-1]["flux"]) if p10 else None
        data = {"kp": kp, "kp_time": last_kp.get("time_tag"), "geomagnetic_scale": _scale_g(kp),
                "proton_flux_10mev_pfu": round(flux, 3) if flux is not None else None,
                "proton_time": p10[-1]["time_tag"] if p10 else None,
                "radiation_storm_scale": _scale_s(flux) if flux is not None else "unknown",
                "source": "NOAA SWPC public JSON"}
        msg = f"Kp {kp:.2f} ({data['geomagnetic_scale']}), >=10 MeV protons {flux:.2f} pfu ({data['radiation_storm_scale']})" if flux is not None else f"Kp {kp:.2f}"
        return Result(True, msg, data)


class Health01Peer(Connector):
    id = "health01_peer"
    name = "Another HEALTH-01 server"
    description = "A second HEALTH-01 installation (for example the ground copy or a backup). Checks it is reachable and which version it runs."
    default_url = "http://localhost:8000"
    url_hint = "http://host:8000"

    def check(self, url: str, settings: dict) -> Result:
        h = self.get_json(url.rstrip("/") + "/api/v1/health")
        return Result(h.get("status") == "ok", f"{h.get('app', 'server')} {h.get('version', '')}: {h.get('status')}",
                      {k: h.get(k) for k in ("app", "version", "status", "database", "assistant_mode", "assistant_model")})


class OllamaServer(Connector):
    id = "ollama"
    name = "Ollama / local LLM server"
    description = "An Ollama server for the assistant and fine-tuned models. Lists the models it has."
    default_url = "http://localhost:11434"
    url_hint = "http://host:11434"

    def check(self, url: str, settings: dict) -> Result:
        tags = self.get_json(url.rstrip("/") + "/api/tags")
        models = [{"name": m.get("name"), "size_gb": round((m.get("size") or 0) / 1e9, 2),
                   "family": (m.get("details") or {}).get("family"),
                   "parameters": (m.get("details") or {}).get("parameter_size"),
                   "quantization": (m.get("details") or {}).get("quantization_level")} for m in tags.get("models", [])]
        return Result(True, f"{len(models)} model(s) available", {"models": models})


class JsonFeed(Connector):
    id = "json_feed"
    name = "Any JSON URL"
    description = ("Adaptive connector: point it at any URL that returns JSON (a lab system, a sensor gateway, a "
                   "public API). Shows the top-level structure so you can decide how to use it.")
    default_url = ""

    def check(self, url: str, settings: dict) -> Result:
        j = self.get_json(url, headers=({"Authorization": f"Bearer {settings['token']}"} if settings.get("token") else None))
        if isinstance(j, list):
            shape = {"type": "list", "length": len(j), "first_item_keys": sorted(j[0].keys())[:30] if j and isinstance(j[0], dict) else None}
        elif isinstance(j, dict):
            shape = {"type": "object", "keys": sorted(j.keys())[:40]}
        else:
            shape = {"type": type(j).__name__}
        return Result(True, f"JSON {shape['type']} received", {"shape": shape, "fetched_at": datetime.now(timezone.utc).isoformat()})


CONNECTORS: list[type[Connector]] = [NoaaSpaceWeather, Health01Peer, OllamaServer, JsonFeed]
