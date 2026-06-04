"""Maintenance / liveness check — is this a dead or abandoned project?

An AI happily recommends packages that were last touched years ago. We flag
archived/disabled repos and long-stale activity using the most recent of the
GitHub ``pushed_at`` and the registry's last release.
"""

from __future__ import annotations

from typing import Optional

from .._dates import age_days
from ..models import Finding, Grade, Severity
from .base import Check, CheckContext


def _newest_activity_days(report) -> Optional[float]:
    candidates = []
    gh = report.meta.get("github") or {}
    for key in ("pushed_at", "updated_at"):
        d = age_days(gh.get(key))
        if d is not None:
            candidates.append(d)
    reg = report.meta.get("registry") or {}
    d = age_days(reg.get("last_release"))
    if d is not None:
        candidates.append(d)
    return min(candidates) if candidates else None


class MaintenanceCheck(Check):
    id = "maintenance"

    def run(self, report, ctx: CheckContext) -> None:
        gh = report.meta.get("github") or {}
        reg = report.meta.get("registry") or {}

        if gh.get("archived"):
            report.add(Finding(
                self.id, Severity.HIGH, "Repository is archived",
                "The maintainer marked it read-only/unmaintained. No future fixes.",
                Grade.WARN,
            ))
            return
        if gh.get("disabled"):
            report.add(Finding(
                self.id, Severity.HIGH, "Repository is disabled",
                "GitHub has disabled this repo.", Grade.WARN,
            ))
            return
        if reg.get("deprecated"):
            report.add(Finding(
                self.id, Severity.HIGH, "Package marked deprecated",
                "The maintainer flagged this package as deprecated.", Grade.WARN,
            ))
            return

        days = _newest_activity_days(report)
        if days is None:
            return
        years = days / 365.0
        if days >= ctx.stale_days_danger:
            report.add(Finding(
                self.id, Severity.MEDIUM,
                f"Likely abandoned (no activity in ~{years:.1f} years)",
                "No commits or releases for a long time — expect no support or "
                "security fixes.",
                Grade.WARN,
            ))
        elif days >= ctx.stale_days_warn:
            report.add(Finding(
                self.id, Severity.LOW,
                f"Stale (no activity in ~{int(days)} days)",
                "Activity has slowed; verify it still fits your needs.",
                Grade.WARN,
            ))
