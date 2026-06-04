"""Fetch GitHub repo metadata for packages that link to one.

This is mostly a *data provider*: it populates ``report.meta['github']`` with
stars/license/dates/archived so the license, maintenance and fake-star checks
can reason about it. It only emits a finding for the positive case (transparency
about which repo backs the package); risk findings belong to the later checks.
"""

from __future__ import annotations

from ..models import Ecosystem, Finding, Grade, Severity
from ..github import fetch_repo
from .base import Check, CheckContext


class GitHubMetaCheck(Check):
    id = "github_meta"

    def applies(self, report, ctx: CheckContext) -> bool:
        # GitHub items already have their data from the existence check.
        return report.item.ecosystem is not Ecosystem.GITHUB

    def run(self, report, ctx: CheckContext) -> None:
        if report.meta.get("github"):
            return  # already fetched
        gh = report.meta.get("github_resolved")
        if not gh:
            return  # no upstream repo link discovered — nothing to do
        res = fetch_repo(ctx.http, gh["owner"], gh["repo"])
        if res.get("status") != "ok":
            report.meta["github_status"] = res.get("status")
            return
        data = res["data"]
        report.meta["github"] = data
        report.add(Finding(
            self.id, Severity.INFO,
            f"Backed by github.com/{data.get('full_name')} ({data.get('stars', 0)}★)",
            data.get("description", "")[:160],
            Grade.OK,
        ))
