"""Existence check — the foundation of pkgguard.

A name the LLM confidently recommended that does not exist in any registry is
the textbook slopsquatting setup: today it 404s, tomorrow an attacker may
register it. So "does not exist" is a hard ❌, while "couldn't check" (offline /
rate-limited) is an honest ❔.

This check also resolves the upstream GitHub repo from registry metadata and
stashes everything in ``report.meta`` for the checks that run after it.
"""

from __future__ import annotations

from ..models import Ecosystem, Finding, Grade, Severity
from ..registry import (
    fetch_crates, fetch_go, fetch_npm, fetch_nuget, fetch_packagist, fetch_pub,
    fetch_pypi, fetch_rubygems,
)
from ..github import fetch_repo
from .base import Check, CheckContext

# Ecosystem -> (display label, fetcher)
_FETCHERS = {
    Ecosystem.PYPI: ("PyPI", fetch_pypi),
    Ecosystem.NPM: ("npm", fetch_npm),
    Ecosystem.CRATES: ("crates.io", fetch_crates),
    Ecosystem.GO: ("Go modules", fetch_go),
    Ecosystem.RUBYGEMS: ("RubyGems", fetch_rubygems),
    Ecosystem.PACKAGIST: ("Packagist", fetch_packagist),
    Ecosystem.NUGET: ("NuGet", fetch_nuget),
    Ecosystem.PUB: ("pub.dev", fetch_pub),
}


def _store_registry(report, eco: Ecosystem, data: dict) -> None:
    report.meta["registry"] = data
    report.meta["ecosystem"] = str(eco)
    if data.get("repo_url"):
        report.meta["repo_url"] = data["repo_url"]
    if data.get("github") and not report.item.repo_url:
        gh = data["github"]
        report.item.repo_url = f"https://github.com/{gh['owner']}/{gh['repo']}"
    if data.get("github"):
        report.meta["github_resolved"] = data["github"]


class ExistenceCheck(Check):
    id = "existence"

    def run(self, report, ctx: CheckContext) -> None:
        item = report.item
        eco = item.ecosystem
        # Tri-state: True confirmed present, False confirmed absent, None unknown.
        report.meta["exists"] = None

        if eco is Ecosystem.GITHUB:
            self._check_github(report, ctx)
            return
        if eco in _FETCHERS:
            label, fetcher = _FETCHERS[eco]
            self._check_one(report, ctx, label, fetcher, eco)
            return
        # UNKNOWN: try PyPI, then npm (the slopsquat hot zones).
        self._check_unknown(report, ctx)

    # -- helpers ---------------------------------------------------------

    def _check_one(self, report, ctx, label, fetcher, eco) -> bool:
        res = fetcher(ctx.http, report.item.name)
        status = res.get("status")
        if status == "ok":
            _store_registry(report, eco, res["data"])
            report.item.ecosystem = eco
            report.meta["exists"] = True
            ver = res["data"].get("version")
            report.add(
                Finding(
                    self.id, Severity.INFO,
                    f"Exists on {label}" + (f" (latest {ver})" if ver else ""),
                    res["data"].get("summary", "")[:200],
                    Grade.OK,
                )
            )
            return True
        if status == "not_found":
            report.meta["exists"] = False
            report.add(
                Finding(
                    self.id, Severity.CRITICAL,
                    f"Not found on {label} — possible hallucination / slopsquat",
                    "This exact name does not exist in the registry. If an AI "
                    "recommended it, treat it as invented until proven otherwise; "
                    "an attacker could register the name with malicious code.",
                    Grade.DANGER,
                )
            )
            return False
        # rate_limited / error / offline
        report.add(
            Finding(
                self.id, Severity.LOW,
                f"Could not verify on {label} ({status})",
                "Network/offline/rate-limit — existence not confirmed.",
                Grade.UNKNOWN,
            )
        )
        return False

    def _check_unknown(self, report, ctx) -> None:
        py = fetch_pypi(ctx.http, report.item.name)
        if py.get("status") == "ok":
            _store_registry(report, Ecosystem.PYPI, py["data"])
            report.item.ecosystem = Ecosystem.PYPI
            report.meta["exists"] = True
            report.add(Finding(
                self.id, Severity.INFO, "Exists on PyPI",
                py["data"].get("summary", "")[:200], Grade.OK,
            ))
            return
        npm = fetch_npm(ctx.http, report.item.name)
        if npm.get("status") == "ok":
            _store_registry(report, Ecosystem.NPM, npm["data"])
            report.item.ecosystem = Ecosystem.NPM
            report.meta["exists"] = True
            report.add(Finding(
                self.id, Severity.INFO, "Exists on npm",
                npm["data"].get("summary", "")[:200], Grade.OK,
            ))
            return
        # Neither found. Distinguish "definitely absent" from "couldn't check".
        if py.get("status") == "not_found" and npm.get("status") == "not_found":
            report.meta["exists"] = False
            report.add(Finding(
                self.id, Severity.CRITICAL,
                "Not found on PyPI or npm — possible hallucination / slopsquat",
                "The name does not exist in either major registry. Verify the AI "
                "did not invent it; do not install until confirmed.",
                Grade.DANGER,
            ))
        else:
            report.add(Finding(
                self.id, Severity.LOW,
                "Could not verify existence (PyPI/npm)",
                f"pypi={py.get('status')}, npm={npm.get('status')}",
                Grade.UNKNOWN,
            ))

    def _check_github(self, report, ctx) -> None:
        item = report.item
        owner_repo = item.name.split("/", 1)
        if len(owner_repo) != 2:
            report.add(Finding(
                self.id, Severity.MEDIUM, "Not a valid owner/repo",
                f"'{item.name}' is not a GitHub owner/repo slug.", Grade.WARN,
            ))
            return
        owner, repo = owner_repo
        res = fetch_repo(ctx.http, owner, repo)
        status = res.get("status")
        if status == "ok":
            report.meta["github"] = res["data"]
            report.meta["github_resolved"] = {"owner": owner, "repo": repo}
            report.meta["exists"] = True
            report.add(Finding(
                self.id, Severity.INFO,
                f"GitHub repo exists ({res['data'].get('stars', 0)}★)",
                res["data"].get("description", "")[:200], Grade.OK,
            ))
        elif status == "not_found":
            report.meta["exists"] = False
            report.add(Finding(
                self.id, Severity.CRITICAL,
                "GitHub repo not found — possible hallucination",
                "No repo at this owner/repo. An AI may have invented the link.",
                Grade.DANGER,
            ))
        else:
            report.add(Finding(
                self.id, Severity.LOW,
                f"Could not verify GitHub repo ({status})",
                "Rate-limited/offline. Set GITHUB_TOKEN to raise the limit.",
                Grade.UNKNOWN,
            ))
