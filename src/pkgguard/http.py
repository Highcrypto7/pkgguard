"""Tiny stdlib HTTP client used by all registry/GitHub lookups.

Deliberately dependency-free (urllib) so the core engine installs with zero
third-party packages and works behind corporate proxies that already trust the
system CA bundle. Features we actually need:

* per-run in-memory response cache (the same package may be looked up by
  several checks),
* short timeouts so one slow registry can't hang a whole report,
* an ``offline`` switch that makes every request fail fast,
* optional bearer token (GitHub) to raise rate limits.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

__all__ = ["HttpResponse", "HttpClient", "OfflineError"]

USER_AGENT = "pkgguard/0.1 (+https://github.com/Highcrypto7/pkgguard)"


class OfflineError(RuntimeError):
    """Raised when a request is attempted while running in offline mode."""


@dataclass
class HttpResponse:
    status: int
    url: str
    body: bytes
    headers: Dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    def json(self) -> Any:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


@dataclass
class HttpClient:
    timeout: float = 8.0
    offline: bool = False
    github_token: Optional[str] = None
    # Optional persistent cache (pkgguard.cache.DiskCache); None disables it.
    cache: Optional[Any] = None
    # url -> (response | exception); both are cached for the run.
    _cache: Dict[str, Tuple[Optional[HttpResponse], Optional[Exception]]] = field(
        default_factory=dict
    )

    def flush(self) -> None:
        """Persist the disk cache (no-op if caching is disabled)."""
        if self.cache is not None:
            self.cache.flush()

    def _from_disk(self, url: str) -> Optional[HttpResponse]:
        if self.cache is None:
            return None
        try:
            hit = self.cache.get(url)
            if not hit:
                return None
            return HttpResponse(
                status=int(hit["status"]),
                url=url,
                body=str(hit["body"]).encode("utf-8"),
                headers=hit.get("headers", {}),
            )
        except (KeyError, TypeError, ValueError, AttributeError):
            # Corrupt / old-schema cache entry: ignore it, fetch fresh.
            return None

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        accept: str = "application/json",
    ) -> HttpResponse:
        """GET ``url``. 4xx/5xx are returned as responses, not raised.

        Network failures (DNS, timeout, refused) raise ``urllib.error.URLError``.
        Offline mode raises :class:`OfflineError` (unless a fresh disk-cache
        entry can satisfy the request).
        """
        if url in self._cache:
            resp, exc = self._cache[url]
            if exc is not None:
                raise exc
            assert resp is not None
            return resp

        # A fresh disk-cache entry serves the request even when offline.
        disk = self._from_disk(url)
        if disk is not None:
            self._cache[url] = (disk, None)
            return disk

        if self.offline:
            exc: Exception = OfflineError(f"offline mode: skipped {url}")
            self._cache[url] = (None, exc)
            raise exc

        req_headers = {"User-Agent": USER_AGENT, "Accept": accept}
        if headers:
            req_headers.update(headers)
        if self.github_token and "api.github.com" in url:
            req_headers.setdefault("Authorization", f"Bearer {self.github_token}")

        req = urllib.request.Request(url, headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                resp = HttpResponse(
                    status=r.status,
                    url=r.geturl(),
                    body=r.read(),
                    headers={k.lower(): v for k, v in r.headers.items()},
                )
        except urllib.error.HTTPError as e:
            # HTTP errors are useful signal (404 = does not exist), keep them.
            resp = HttpResponse(
                status=e.code,
                url=url,
                body=e.read() if hasattr(e, "read") else b"",
                headers={k.lower(): v for k, v in (e.headers or {}).items()},
            )
        except Exception as e:  # URLError, timeout, ssl, etc.
            self._cache[url] = (None, e)
            raise

        self._cache[url] = (resp, None)
        if self.cache is not None:
            self.cache.put(url, resp.status, resp.body, resp.headers)
        return resp

    def post_json(self, url: str, payload: Any,
                  accept: str = "application/json") -> HttpResponse:
        """POST a JSON ``payload`` and return the response.

        Cached (in-memory + disk) under a key derived from the URL and body so
        repeated identical queries (e.g. OSV lookups) are cheap and work offline.
        """
        body_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        key = url + "#" + hashlib.sha1(body_bytes).hexdigest()

        if key in self._cache:
            resp, exc = self._cache[key]
            if exc is not None:
                raise exc
            assert resp is not None
            return resp

        disk = self._from_disk(key)
        if disk is not None:
            self._cache[key] = (disk, None)
            return disk

        if self.offline:
            exc2: Exception = OfflineError(f"offline mode: skipped POST {url}")
            self._cache[key] = (None, exc2)
            raise exc2

        req = urllib.request.Request(
            url, data=body_bytes, method="POST",
            headers={"User-Agent": USER_AGENT, "Accept": accept,
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                resp = HttpResponse(status=r.status, url=url, body=r.read(),
                                    headers={k.lower(): v for k, v in r.headers.items()})
        except urllib.error.HTTPError as e:
            resp = HttpResponse(status=e.code, url=url,
                                body=e.read() if hasattr(e, "read") else b"",
                                headers={k.lower(): v for k, v in (e.headers or {}).items()})
        except Exception as e:
            self._cache[key] = (None, e)
            raise

        self._cache[key] = (resp, None)
        if self.cache is not None:
            self.cache.put(key, resp.status, resp.body, resp.headers)
        return resp

    def get_json_or_none(self, url: str, **kwargs: Any) -> Optional[Any]:
        """GET and parse JSON; return ``None`` on 404, network error, or bad JSON.

        Convenience for "does this exist / what's its metadata" lookups where a
        missing resource is an expected outcome, not an error.
        """
        try:
            resp = self.get(url, **kwargs)
        except Exception:
            return None
        if resp.status == 404:
            return None
        if not resp.ok:
            return None
        try:
            return resp.json()
        except Exception:
            return None
