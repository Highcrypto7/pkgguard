"""RubyGems existence + metadata (public API, no key)."""

from __future__ import annotations

from typing import Any, Dict

from ..http import HttpClient
from ..parse.normalize import github_owner_repo


def fetch_rubygems(http: HttpClient, name: str) -> Dict[str, Any]:
    url = f"https://rubygems.org/api/v1/gems/{name}.json"
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

    licenses = data.get("licenses") or []
    repo_url = data.get("source_code_uri") or data.get("homepage_uri") or ""
    gh = github_owner_repo(repo_url)
    return {
        "status": "ok",
        "data": {
            "name": data.get("name") or name,
            "summary": data.get("info") or "",
            "version": data.get("version"),
            "license": ", ".join(licenses) if isinstance(licenses, list) else (licenses or ""),
            "repo_url": repo_url,
            "github": {"owner": gh[0], "repo": gh[1]} if gh else None,
            "downloads_total": data.get("downloads"),
        },
    }
