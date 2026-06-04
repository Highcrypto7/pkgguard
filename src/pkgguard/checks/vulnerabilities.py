"""Known-vulnerability check via OSV.dev.

Parity with the security dimension of tools like sloppy-joe / depscope: an
AI-recommended package that resolves fine may still carry known CVEs in its
current version. We flag those (⚠️) with their identifiers so you can decide
whether a fixed version exists.
"""

from __future__ import annotations

from ..models import Ecosystem, Finding, Grade, Severity
from ..registry.osv import fetch_vulns, osv_ecosystem
from .base import Check, CheckContext


class VulnerabilityCheck(Check):
    id = "vulnerabilities"

    def applies(self, report, ctx: CheckContext) -> bool:
        return (
            not ctx.offline
            and report.meta.get("exists") is True
            and osv_ecosystem(report.item.ecosystem) is not None
        )

    def run(self, report, ctx: CheckContext) -> None:
        reg = report.meta.get("registry") or {}
        version = report.item.version or reg.get("version")
        res = fetch_vulns(ctx.http, report.item.ecosystem, report.item.name, version)
        if res.get("status") != "ok":
            return
        vulns = res.get("vulns") or []
        if not vulns:
            return
        report.meta["vulnerabilities"] = vulns
        ids = ", ".join(v["cve"] for v in vulns[:4] if v.get("cve"))
        extra = f" (+{len(vulns) - 4} more)" if len(vulns) > 4 else ""
        ver_note = f" in {version}" if version else ""
        report.add(Finding(
            self.id, Severity.HIGH,
            f"{len(vulns)} known vulnerability(ies){ver_note}",
            f"OSV reports: {ids}{extra}. Check for a patched version before using it.",
            Grade.WARN,
        ))
