"""GitHub repo lookups.

Unauthenticated GitHub allows ~60 requests/hour per IP; set ``GITHUB_TOKEN``
(or ``GH_TOKEN``) to raise this to 5000/hour. We always treat 403/429 as
"rate limited / could not check" — never as "repo does not exist" — so a
throttled run degrades to UNKNOWN instead of falsely crying hallucination.
"""

from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

from ..http import HttpClient

API = "https://api.github.com"


def _decode_content(payload: Any, cap: int = 60_000) -> Optional[str]:
    """Decode a GitHub contents API base64 blob to text (bounded)."""
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        return None
    try:
        raw = base64.b64decode(payload.get("content", ""))
    except Exception:
        return None
    return raw[:cap].decode("utf-8", errors="replace")


def fetch_license_text(http: HttpClient, owner: str, repo: str) -> Optional[str]:
    """Fetch the repo's LICENSE file text (for custom/NOASSERTION licenses)."""
    data = http.get_json_or_none(f"{API}/repos/{owner}/{repo}/license")
    return _decode_content(data) if data else None


def fetch_readme(http: HttpClient, owner: str, repo: str) -> Optional[str]:
    """Fetch the repo's README text."""
    data = http.get_json_or_none(f"{API}/repos/{owner}/{repo}/readme")
    return _decode_content(data) if data else None


def _status_of(resp) -> str:
    if resp.status == 404:
        return "not_found"
    if resp.status in (401, 403, 429):
        return "rate_limited"
    if resp.ok:
        return "ok"
    return "error"


def fetch_repo(http: HttpClient, owner: str, repo: str) -> Dict[str, Any]:
    url = f"{API}/repos/{owner}/{repo}"
    try:
        resp = http.get(url)
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    status = _status_of(resp)
    if status != "ok":
        return {"status": status, "code": resp.status}
    try:
        d = resp.json()
    except Exception as e:
        return {"status": "error", "error": repr(e)}

    lic = d.get("license") or {}
    return {
        "status": "ok",
        "data": {
            "full_name": d.get("full_name"),
            "html_url": d.get("html_url"),
            "description": d.get("description") or "",
            "stars": d.get("stargazers_count", 0),
            "forks": d.get("forks_count", 0),
            "open_issues": d.get("open_issues_count", 0),
            "watchers": d.get("subscribers_count"),
            "created_at": d.get("created_at"),
            "pushed_at": d.get("pushed_at"),
            "updated_at": d.get("updated_at"),
            "archived": bool(d.get("archived")),
            "disabled": bool(d.get("disabled")),
            "is_fork": bool(d.get("fork")),
            "license_spdx": (lic.get("spdx_id") or "") if isinstance(lic, dict) else "",
            "license_name": (lic.get("name") or "") if isinstance(lic, dict) else "",
            "default_branch": d.get("default_branch"),
            "owner_type": (d.get("owner") or {}).get("type"),
        },
    }


def _star_page(http: HttpClient, owner: str, repo: str, page: int) -> List[str]:
    """Return starred_at timestamps for one page (100) of stargazers."""
    url = f"{API}/repos/{owner}/{repo}/stargazers?per_page=100&page={page}"
    try:
        # star+json adds the starred_at timestamp to each entry.
        resp = http.get(url, accept="application/vnd.github.star+json")
    except Exception:
        return []
    if not resp.ok:
        return []
    try:
        rows = resp.json()
    except Exception:
        return []
    out = []
    for r in rows:
        if isinstance(r, dict) and r.get("starred_at"):
            out.append(r["starred_at"])
    return out


def fetch_stargazers_sample(
    http: HttpClient, owner: str, repo: str, total_stars: int
) -> Dict[str, Any]:
    """Sample star timestamps from the first and last page to spot bursts.

    Cheap (1-2 API calls): enough to flag the classic fake-star signature where
    a large fraction of stars land in a tiny time window.
    """
    first = _star_page(http, owner, repo, 1)
    timestamps = list(first)
    if total_stars > 100:
        last_page = (total_stars + 99) // 100
        if last_page > 1:
            timestamps += _star_page(http, owner, repo, last_page)
    return {"timestamps": sorted(timestamps), "sampled": len(timestamps)}

def fetch_skill_files(
    http: HttpClient, owner: str, repo: str, limit: int = 12
) -> Dict[str, str]:
    """Return {path: text} for the repo's SKILL.md files, or {}.

    Agent skills ship as a folder with a ``SKILL.md`` inside, distributed via
    GitHub rather than PyPI/npm — so ``fetch_source_files`` never sees them, and
    the payload of a malicious skill is usually *the instructions themselves*
    (plain markdown telling the agent to read a credential and POST it), not
    compiled code. That combination is why this needs its own fetch.

    One recursive tree call locates the files; contents are fetched per file and
    capped, so a skill monorepo with hundreds of entries cannot blow up the run.
    """
    default_branch = "HEAD"
    tree = http.get_json_or_none(
        f"{API}/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1"
    )
    if not isinstance(tree, dict):
        return {}
    paths = [
        n.get("path", "")
        for n in (tree.get("tree") or [])
        if isinstance(n, dict)
        and n.get("type") == "blob"
        and n.get("path", "").rsplit("/", 1)[-1].upper() == "SKILL.MD"
    ]
    out: Dict[str, str] = {}
    for path in paths[:limit]:
        data = http.get_json_or_none(f"{API}/repos/{owner}/{repo}/contents/{path}")
        text = _decode_content(data) if data else None
        if text:
            out[path] = text
    return out
