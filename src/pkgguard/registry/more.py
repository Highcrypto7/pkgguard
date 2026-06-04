"""Existence + metadata for additional ecosystems: Packagist, NuGet, Pub."""

from __future__ import annotations

from typing import Any, Dict
from urllib.parse import quote

from ..http import HttpClient
from ..parse.normalize import github_owner_repo


def _status(resp) -> str:
    if resp.status == 404:
        return "not_found"
    if resp.status in (403, 429):
        return "rate_limited"
    return "ok" if resp.ok else "error"


def fetch_packagist(http: HttpClient, name: str) -> Dict[str, Any]:
    # Packagist names are "vendor/package".
    if "/" not in name:
        return {"status": "not_found"}
    url = f"https://repo.packagist.org/p2/{name.lower()}.json"
    try:
        resp = http.get(url)
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    st = _status(resp)
    if st != "ok":
        return {"status": st}
    try:
        data = resp.json()
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    versions = (data.get("packages") or {}).get(name.lower()) or []
    latest = versions[0] if versions else {}
    lic = latest.get("license") or []
    repo_url = (latest.get("source") or {}).get("url") or latest.get("homepage") or ""
    gh = github_owner_repo(repo_url)
    return {
        "status": "ok",
        "data": {
            "name": name,
            "summary": latest.get("description") or "",
            "version": latest.get("version"),
            "license": ", ".join(lic) if isinstance(lic, list) else str(lic or ""),
            "repo_url": repo_url,
            "github": {"owner": gh[0], "repo": gh[1]} if gh else None,
            "release_count": len(versions),
        },
    }


def fetch_nuget(http: HttpClient, name: str) -> Dict[str, Any]:
    nid = name.lower()
    url = f"https://api.nuget.org/v3-flatcontainer/{quote(nid)}/index.json"
    try:
        resp = http.get(url)
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    st = _status(resp)
    if st != "ok":
        return {"status": st}
    try:
        data = resp.json()
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    versions = data.get("versions") or []
    if not versions:
        return {"status": "not_found"}
    return {
        "status": "ok",
        "data": {
            "name": name,
            "summary": "",
            "version": versions[-1],
            "license": "",  # not in flatcontainer index; left for OSV/github
            "repo_url": "",
            "github": None,
            "release_count": len(versions),
        },
    }


def fetch_pub(http: HttpClient, name: str) -> Dict[str, Any]:
    url = f"https://pub.dev/api/packages/{quote(name)}"
    try:
        resp = http.get(url)
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    st = _status(resp)
    if st != "ok":
        return {"status": st}
    try:
        data = resp.json()
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    latest = data.get("latest") or {}
    pubspec = latest.get("pubspec") or {}
    repo_url = pubspec.get("repository") or pubspec.get("homepage") or ""
    gh = github_owner_repo(repo_url)
    return {
        "status": "ok",
        "data": {
            "name": data.get("name") or name,
            "summary": pubspec.get("description") or "",
            "version": latest.get("version"),
            "license": "",  # pub.dev exposes license separately; keep simple
            "repo_url": repo_url,
            "github": {"owner": gh[0], "repo": gh[1]} if gh else None,
        },
    }
