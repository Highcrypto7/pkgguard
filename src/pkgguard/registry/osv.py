"""Known-vulnerability lookups via OSV.dev (open, key-free).

OSV aggregates GHSA, PyPA, RustSec, Go, RubySec and more, so one query covers
every ecosystem pkgguard supports. We query the specific resolved version when we
have it, falling back to all-versions otherwise.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..http import HttpClient
from ..models import Ecosystem

# pkgguard ecosystem -> OSV ecosystem string
_OSV_ECO = {
    Ecosystem.PYPI: "PyPI",
    Ecosystem.NPM: "npm",
    Ecosystem.CRATES: "crates.io",
    Ecosystem.GO: "Go",
    Ecosystem.RUBYGEMS: "RubyGems",
    Ecosystem.PACKAGIST: "Packagist",
    Ecosystem.NUGET: "NuGet",
    Ecosystem.PUB: "Pub",
}


def osv_ecosystem(eco: Ecosystem) -> Optional[str]:
    return _OSV_ECO.get(eco)


def fetch_vulns(http: HttpClient, eco: Ecosystem, name: str,
                version: Optional[str]) -> Dict[str, Any]:
    osv_eco = _OSV_ECO.get(eco)
    if not osv_eco:
        return {"status": "skip"}
    payload: Dict[str, Any] = {"package": {"name": name, "ecosystem": osv_eco}}
    if version:
        payload["version"] = version
    try:
        resp = http.post_json("https://api.osv.dev/v1/query", payload)
    except Exception as e:
        return {"status": "error", "error": repr(e)}
    if not resp.ok:
        return {"status": "error", "code": resp.status}
    try:
        data = resp.json()
    except Exception as e:
        return {"status": "error", "error": repr(e)}

    vulns: List[Dict[str, Any]] = data.get("vulns") or []
    out = []
    for v in vulns:
        sev = ""
        for s in v.get("severity") or []:
            if s.get("type") in ("CVSS_V3", "CVSS_V4"):
                sev = s.get("score", "")
                break
        aliases = v.get("aliases") or []
        cve = next((a for a in aliases if a.startswith("CVE-")), v.get("id"))
        out.append({
            "id": v.get("id"),
            "cve": cve,
            "summary": (v.get("summary") or v.get("details") or "")[:160],
            "severity": sev,
        })
    return {"status": "ok", "vulns": out}
