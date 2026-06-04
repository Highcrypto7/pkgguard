"""npm existence + metadata via the public registry (no key required)."""

from __future__ import annotations

from typing import Any, Dict
from urllib.parse import quote

from ..http import HttpClient
from ..parse.normalize import github_owner_repo


def _repo_url(latest: Dict[str, Any], top: Dict[str, Any]) -> str:
    for src in (latest, top):
        repo = src.get("repository")
        if isinstance(repo, dict) and repo.get("url"):
            return repo["url"]
        if isinstance(repo, str) and repo:
            return repo
    hp = latest.get("homepage") or top.get("homepage") or ""
    return hp if isinstance(hp, str) else ""


def _license_str(latest: Dict[str, Any], top: Dict[str, Any]) -> str:
    for src in (latest, top):
        lic = src.get("license")
        if isinstance(lic, str) and lic:
            return lic
        if isinstance(lic, dict) and lic.get("type"):
            return lic["type"]
    return ""


def fetch_npm(http: HttpClient, name: str) -> Dict[str, Any]:
    url = f"https://registry.npmjs.org/{quote(name, safe='@/')}"
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

    dist_tags = data.get("dist-tags") or {}
    latest_ver = dist_tags.get("latest")
    versions = data.get("versions") or {}
    latest = versions.get(latest_ver, {}) if isinstance(versions, dict) else {}
    times = data.get("time") or {}
    repo_url = _repo_url(latest, data)
    gh = github_owner_repo(repo_url)
    return {
        "status": "ok",
        "data": {
            "name": data.get("name") or name,
            "summary": data.get("description") or "",
            "version": latest_ver,
            "license": _license_str(latest, data),
            "repo_url": repo_url,
            "github": {"owner": gh[0], "repo": gh[1]} if gh else None,
            "release_count": len(versions) if isinstance(versions, dict) else 0,
            "first_release": times.get("created"),
            # Prefer the latest version's publish time over `modified` (which is
            # bumped by metadata-only changes like deprecation/owner edits).
            "last_release": times.get(latest_ver) or times.get("modified"),
            "deprecated": bool(latest.get("deprecated")),
            "has_install_scripts": bool(
                (latest.get("scripts") or {}).get("install")
                or (latest.get("scripts") or {}).get("preinstall")
                or (latest.get("scripts") or {}).get("postinstall")
            ),
            "maintainers": len(data.get("maintainers") or []),
        },
    }
