"""Popularity / legitimacy signal from monthly download counts.

Downloads are a precision-safe reassurance signal: a package pulling millions of
installs a month is almost certainly the real thing, while a *brand-new* package
with near-zero downloads warrants a second look. We deliberately do NOT warn on
low downloads alone — plenty of legitimate niche packages are quiet — only when
it compounds an already-suspicious freshly-registered look-alike.
"""

from __future__ import annotations

from .._dates import age_days
from ..models import Ecosystem, Finding, Grade, Severity
from ..registry.downloads import npm_downloads_last_month, pypi_downloads_last_month
from .base import Check, CheckContext


def _humanize(n: int) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


class PopularityCheck(Check):
    id = "popularity"

    def applies(self, report, ctx: CheckContext) -> bool:
        return (
            not ctx.offline
            and report.meta.get("exists") is True
            and report.item.ecosystem in (Ecosystem.PYPI, Ecosystem.NPM)
        )

    def run(self, report, ctx: CheckContext) -> None:
        eco = report.item.ecosystem
        if eco is Ecosystem.PYPI:
            dl = pypi_downloads_last_month(ctx.http, report.item.name)
        else:
            dl = npm_downloads_last_month(ctx.http, report.item.name)
        if dl is None:
            return
        report.meta["downloads_last_month"] = dl

        reg = report.meta.get("registry") or {}
        first = reg.get("first_release")
        age = age_days(first) if first else None
        is_new = age is not None and age <= ctx.new_package_days

        if is_new and dl < 100 and report.meta.get("typosquat_match"):
            # New + barely-used + looks like a popular package -> reinforce caution.
            report.add(Finding(
                self.id, Severity.MEDIUM,
                f"Very low adoption ({_humanize(dl)}/mo) for a new look-alike",
                "Freshly registered, almost no downloads, and resembles a popular "
                "package — consistent with a squat. Prefer the established package.",
                Grade.WARN,
            ))
        elif dl >= 10_000:
            report.add(Finding(
                self.id, Severity.INFO,
                f"Widely used (~{_humanize(dl)} downloads/month)",
                "High adoption is a reassuring legitimacy signal.",
                Grade.OK,
            ))
