"""Go module existence + metadata via the public module proxy (no key).

Go module paths are import paths (e.g. ``github.com/gin-gonic/gin``); the proxy
requires uppercase letters to be escaped as ``!<lower>``.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from ..http import HttpClient
from ..parse.normalize import github_owner_repo


def _escape(module: str) -> str:
    return re.sub(r"[A-Z]", lambda m: "!" + m.group(0).lower(), module)


def fetch_go(http: HttpClient, name: str) -> Dict[str, Any]:
    url = f"https://proxy.golang.org/{_escape(name)}/@latest"
    try:
        resp = http.get(url)
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    if resp.status in (404, 410):
        return {"status": "not_found"}
    if resp.status in (403, 429):
        return {"status": "rate_limited"}
    if not resp.ok:
        return {"status": "error", "code": resp.status}
    try:
        data = resp.json()
    except Exception as e:
        return {"status": "error", "error": repr(e)}

    gh = github_owner_repo(name if name.startswith("github.com") else "")
    repo_url = f"https://{name}" if name.startswith("github.com") else ""
    return {
        "status": "ok",
        "data": {
            "name": name,
            "summary": "",
            "version": data.get("Version"),
            "license": "",  # proxy doesn't expose license; left for github_meta
            "repo_url": repo_url,
            "github": {"owner": gh[0], "repo": gh[1]} if gh else None,
            "last_release": data.get("Time"),
        },
    }
