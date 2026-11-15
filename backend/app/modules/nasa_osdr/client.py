"""Thin client for the public NASA OSDR APIs, with an on-disk cache.

Endpoints used (all public, no key required):
  search   GET {base}/osdr/data/search?term=..&type=cgene&size=..
  metadata GET {base}/osdr/data/osd/meta/{n}
  files    GET {base}/osdr/data/osd/files/{n}
  download GET {base}/geode-py/ws/studies/OSD-{n}/download?source=datamanager&file=..

Lookup order for downloads: runtime cache -> network -> bundled snapshot.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from urllib.parse import quote

import httpx

log = logging.getLogger("hmt.osdr")
SAFE = re.compile(r"[^A-Za-z0-9._\-]")


class OSDRUnavailable(Exception):
    pass


class OSDRClient:
    def __init__(self, base: str, cache_dir: str | Path, snapshot_dir: str | Path | None,
                 timeout: float = 20.0, online: bool = True):
        self.base = base.rstrip("/")
        self.cache = Path(cache_dir)
        self.snapshot = Path(snapshot_dir) if snapshot_dir else None
        self.timeout = timeout
        self.online = online

    @staticmethod
    def num(accession: str) -> str:
        m = re.fullmatch(r"(?:OSD-)?(\d+)", accession.strip())
        if not m:
            raise ValueError(f"invalid OSD accession {accession}")
        return m.group(1)

    def _paths(self, accession: str, name: str) -> list[Path]:
        rel = Path(f"OSD-{self.num(accession)}") / SAFE.sub("_", name)
        paths = [self.cache / rel]
        if self.snapshot:
            paths.append(self.snapshot / rel)
        return paths

    def _get(self, url: str, params: dict | None = None) -> httpx.Response:
        if not self.online:
            raise OSDRUnavailable("NASA online access disabled (NASA_ONLINE=false)")
        try:
            r = httpx.get(url, params=params, timeout=self.timeout, follow_redirects=True,
                          headers={"User-Agent": "health-monitoring-tool-prototype/1.0"})
        except httpx.HTTPError as e:
            raise OSDRUnavailable(f"network error: {e}") from e
        if r.status_code in (401, 403):
            raise OSDRUnavailable(f"restricted ({r.status_code})")
        if r.status_code >= 400:
            raise OSDRUnavailable(f"HTTP {r.status_code}")
        return r

    def _cached_json(self, accession: str, name: str, url: str, refresh: bool) -> dict:
        cache_path, *fallbacks = self._paths(accession, name)
        if cache_path.exists() and not refresh:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        try:
            data = self._get(url).json()
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(data), encoding="utf-8")
            return data
        except OSDRUnavailable:
            for p in [cache_path, *fallbacks]:
                if p.exists():
                    log.info("using cached %s", p)
                    return json.loads(p.read_text(encoding="utf-8"))
            raise

    def study_metadata(self, accession: str, refresh: bool = False) -> dict:
        n = self.num(accession)
        return self._cached_json(accession, "metadata.json", f"{self.base}/osdr/data/osd/meta/{n}", refresh)

    def study_files(self, accession: str, refresh: bool = False) -> dict:
        n = self.num(accession)
        return self._cached_json(accession, "files.json", f"{self.base}/osdr/data/osd/files/{n}", refresh)

    def search(self, term: str, size: int = 25) -> list[dict]:
        r = self._get(f"{self.base}/osdr/data/search", {"term": term, "type": "cgene", "size": size})
        return [h.get("_source", {}) for h in r.json().get("hits", {}).get("hits", [])]

    def download(self, accession: str, filename: str, refresh: bool = False, max_bytes: int = 5_000_000) -> tuple[bytes, str]:
        """Return (content, origin) where origin is cache|network|snapshot."""
        cache_path, *fallbacks = self._paths(accession, filename)
        if cache_path.exists() and not refresh:
            return cache_path.read_bytes(), "cache"
        n = self.num(accession)
        url = (f"{self.base}/geode-py/ws/studies/OSD-{n}/download?source=datamanager&file={quote(filename)}")
        try:
            r = self._get(url)
            if len(r.content) > max_bytes:
                raise OSDRUnavailable(f"file larger than {max_bytes} bytes; skipped")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(r.content)
            return r.content, "network"
        except OSDRUnavailable:
            for p in fallbacks:
                if p.exists():
                    return p.read_bytes(), "snapshot"
            raise
