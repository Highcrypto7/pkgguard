"""PyPI existence + metadata via the public JSON API (no key required).

Returns a status-tagged dict so callers can tell "definitely does not exist"
(404 -> possible hallucination) apart from "couldn't check" (network/offline).
"""

from __future__ import annotations

import re
from typing import Any, Dict

from ..http import HttpClient
from ..parse.normalize import github_owner_repo

# Trove classifier -> short license id, used when the free-text license is blank.
_CLASSIFIER_LICENSE = re.compile(r"License :: (?:OSI Approved :: )?(.+)")


def _pick_repo_url(info: Dict[str, Any]) -> str:
    candidates = []
    purls = info.get("project_urls") or {}
    if isinstance(purls, dict):
        # Prefer source/repo links over homepage.
        for key in ("Source", "Source Code", "Repository", "Code", "GitHub", "Homepage"):
            for k, v in purls.items():
                if k.lower() == key.lower() and v:
                    candidates.append(v)
    candidates.append(info.get("home_page") or "")
    if isinstance(purls, dict):
        candidates.extend(v for v in purls.values() if v)
    for url in candidates:
        if url and "github.com" in url:
            return url
    return ""


def _license_from_classifiers(info: Dict[str, Any]) -> str:
    for c in info.get("classifiers") or []:
        m = _CLASSIFIER_LICENSE.match(c)
        if m and "License" in c:
            val = m.group(1).strip()
            if val and val.lower() != "other/proprietary license":
                return val
            if val:
                return val
    return ""


def _release_dates(data: Dict[str, Any]):
    """Return (earliest, latest) ISO timestamps, compared as real datetimes.

    PyPI mixes ``upload_time_iso_8601`` ("...Z") and ``upload_time`` (space
    form); comparing them as raw strings mis-ranks equal instants, so we parse
    to datetimes for the comparison and return the original ISO strings.
    """
    from .._dates import parse_iso

    earliest = latest = None  # each: (datetime, original_string)
    releases = data.get("releases") or {}
    for files in releases.values():
        if not isinstance(files, list):
            continue
        for f in files:
            ts = f.get("upload_time_iso_8601") or f.get("upload_time")
            dt = parse_iso(ts)
            if dt is None:
                continue
            if earliest is None or dt < earliest[0]:
                earliest = (dt, ts)
            if latest is None or dt > latest[0]:
                latest = (dt, ts)
    return (earliest[1] if earliest else None, latest[1] if latest else None)


def fetch_pypi(http: HttpClient, name: str) -> Dict[str, Any]:
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        resp = http.get(url)
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    if resp.status == 404:
        return {"status": "not_found"}
    if resp.status in (403, 429):
        return {"status": "rate_limited"}
    if not resp.ok:
        return {"status": "error", "code": resp.status}
    try:
        data = resp.json()
    except Exception as e:
        return {"status": "error", "error": repr(e)}

    info = data.get("info") or {}
    earliest, latest = _release_dates(data)
    # Prefer the clean SPDX expression (PEP 639) over the free-text license
    # field (which is often the full license *text*) or trove classifiers.
    license_str = (
        (info.get("license_expression") or "").strip()
        or (info.get("license") or "").strip()
        or _license_from_classifiers(info)
    )
    # If the free-text license is actually the whole license body, drop it in
    # favour of classifiers so downstream matching stays meaningful.
    if len(license_str) > 60:
        license_str = _license_from_classifiers(info) or license_str[:60]
    repo_url = _pick_repo_url(info)
    gh = github_owner_repo(repo_url)
    return {
        "status": "ok",
        "data": {
            "name": info.get("name") or name,
            "summary": info.get("summary") or "",
            "version": info.get("version"),
            "license": license_str,
            "classifiers": info.get("classifiers") or [],
            "repo_url": repo_url,
            "github": {"owner": gh[0], "repo": gh[1]} if gh else None,
            "release_count": len(data.get("releases") or {}),
            "first_release": earliest,
            "last_release": latest,
            "yanked": bool(info.get("yanked")),
            "requires_python": info.get("requires_python"),
            "author": info.get("author") or "",
        },
    }
