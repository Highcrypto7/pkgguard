"""crates.io existence + metadata (public API, no key)."""

from __future__ import annotations

from typing import Any, Dict

from ..http import HttpClient
from ..parse.normalize import github_owner_repo


def fetch_crates(http: HttpClient, name: str) -> Dict[str, Any]:
    url = f"https://crates.io/api/v1/crates/{name}"
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

    crate = data.get("crate") or {}
    versions = data.get("versions") or []
    latest = versions[0] if versions else {}
    repo_url = crate.get("repository") or ""
    gh = github_owner_repo(repo_url)
    return {
        "status": "ok",
        "data": {
            "name": crate.get("name") or name,
            "summary": crate.get("description") or "",
            "version": crate.get("newest_version") or crate.get("max_version"),
            "license": latest.get("license") or "",
            "repo_url": repo_url,
            "github": {"owner": gh[0], "repo": gh[1]} if gh else None,
            "release_count": len(versions),
            "first_release": crate.get("created_at"),
            "last_release": crate.get("updated_at"),
        },
    }
