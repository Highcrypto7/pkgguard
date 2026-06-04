"""Best-effort download-count lookups (popularity / legitimacy signal).

Both endpoints are public and key-free. These are *best effort*: any failure
returns ``None`` and produces no finding, so a flaky stats host never turns a
result UNKNOWN.
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote

from ..http import HttpClient
from ..parse.normalize import normalize_pypi


def pypi_downloads_last_month(http: HttpClient, name: str) -> Optional[int]:
    url = f"https://pypistats.org/api/packages/{normalize_pypi(name)}/recent"
    data = http.get_json_or_none(url)
    if not isinstance(data, dict):
        return None
    d = data.get("data") or {}
    val = d.get("last_month")
    return int(val) if isinstance(val, int) else None


def npm_downloads_last_month(http: HttpClient, name: str) -> Optional[int]:
    url = f"https://api.npmjs.org/downloads/point/last-month/{quote(name, safe='@/')}"
    data = http.get_json_or_none(url)
    if not isinstance(data, dict):
        return None
    val = data.get("downloads")
    return int(val) if isinstance(val, int) else None
