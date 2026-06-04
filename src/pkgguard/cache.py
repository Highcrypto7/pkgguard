"""Optional on-disk HTTP cache.

Registry/GitHub metadata changes slowly, so caching responses makes repeated
runs (and the MCP server / CI integrations) fast and gentle on rate limits. A
cache hit also lets ``--offline`` return real answers from a previous run.

The cache is a single JSON file; we cache successful responses and definitive
404s (a name that doesn't exist stays cached), but never transient 403/429/5xx.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, Optional


def default_cache_path() -> str:
    base = os.environ.get("PKGVET_CACHE_DIR")
    if not base:
        if os.name == "nt":
            root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            base = os.path.join(root, "pkgguard", "cache")
        else:
            base = os.path.join(os.path.expanduser("~"), ".cache", "pkgguard")
    return os.path.join(base, "http-cache.json")


class DiskCache:
    #: Don't persist very large bodies (e.g. PyPI JSON with full release history).
    #: The high-value entries to cache are tiny 404s for hallucinated names and
    #: small-package metadata; huge popular packages resolve fast online anyway.
    MAX_BODY_BYTES = 512 * 1024

    def __init__(self, path: Optional[str] = None, ttl: float = 24 * 3600):
        self.path = path or default_cache_path()
        self.ttl = ttl
        self._data: Dict[str, Any] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                self._data = json.load(fh)
        except Exception:
            self._data = {}

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        entry = self._data.get(url)
        if not isinstance(entry, dict):
            return None
        # Reject malformed / old-schema entries instead of trusting them.
        if "status" not in entry or "body" not in entry:
            return None
        if (time.time() - entry.get("ts", 0)) >= self.ttl:
            return None
        return entry

    def put(self, url: str, status: int, body: bytes, headers: Dict[str, str]) -> None:
        # Only cache definitive results; skip transient failures.
        if not (200 <= status < 300 or status == 404):
            return
        if len(body) > self.MAX_BODY_BYTES:
            return  # too big to be worth persisting
        try:
            text = body.decode("utf-8")  # only cache cleanly-decodable bodies
        except UnicodeDecodeError:
            return
        self._data[url] = {
            "ts": time.time(),
            "status": status,
            "body": text,
            "headers": headers or {},
        }
        self._dirty = True

    def flush(self) -> None:
        if not self._dirty:
            return
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh)
            self._dirty = False
        except Exception:
            pass  # cache is best-effort; never fail a run over it

    def clear(self) -> int:
        n = len(self._data)
        self._data = {}
        self._dirty = True
        self.flush()
        try:
            if os.path.exists(self.path):
                os.remove(self.path)
        except Exception:
            pass
        return n
