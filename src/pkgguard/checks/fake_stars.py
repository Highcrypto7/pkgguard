"""Fake-star / inflated-popularity check (opt-in: ``--deep`` / deep_fake_stars).

Star counts are the #1 trust signal people use to decide whether an AI's repo
suggestion is legit — and they are routinely bought. Research has flagged
millions of fake stars across thousands of repos. Detecting this perfectly
needs heavy per-account analysis; we use a cheap, conservative set of signals
(1-2 extra API calls) and only ever raise a ⚠️, never a hard ❌, because these
are heuristics:

* a large fraction of sampled stars landing in one tight time window (a burst
  buy), and
* implausibly high stars for the repo's age, or stars with almost no forks.

This complements dedicated tools (StarScout, Astronomer, StarGuard).
"""

from __future__ import annotations

from collections import Counter
from typing import List

from .._dates import age_days, parse_iso
from ..github import fetch_stargazers_sample
from ..models import Finding, Grade, Severity
from .base import Check, CheckContext


def _max_window_fraction(timestamps: List[str], window_days: int = 7) -> float:
    """Largest fraction of samples falling inside any ``window_days`` window."""
    dts = sorted(d for d in (parse_iso(t) for t in timestamps) if d is not None)
    if len(dts) < 2:
        return 0.0
    n = len(dts)
    best = 1
    j = 0
    for i in range(n):
        while (dts[i] - dts[j]).total_seconds() > window_days * 86400:
            j += 1
        best = max(best, i - j + 1)
    return best / n


class FakeStarsCheck(Check):
    id = "fake_stars"

    def applies(self, report, ctx: CheckContext) -> bool:
        gh = report.meta.get("github") or {}
        return ctx.deep_fake_stars and gh.get("stars", 0) >= 100

    def run(self, report, ctx: CheckContext) -> None:
        gh = report.meta.get("github") or {}
        stars = gh.get("stars", 0)
        forks = gh.get("forks", 0) or 0
        gh_resolved = report.meta.get("github_resolved") or {}
        owner, repo = gh_resolved.get("owner"), gh_resolved.get("repo")

        reasons = []

        # Signal A: implausible stars for the repo's age.
        age = age_days(gh.get("created_at"))
        if age is not None and age < 90 and stars > 3000:
            reasons.append(
                f"{stars}★ on a repo only ~{int(age)} days old (very rapid growth)"
            )

        # Signal B: lots of stars but almost no forks (organic projects get forks).
        if stars >= 1000 and forks <= max(2, stars // 1000) and forks < 5:
            reasons.append(f"{stars}★ but only {forks} fork(s)")

        # Signal C: a burst of stars in a tiny window (requires sampling).
        if owner and repo:
            sample = fetch_stargazers_sample(ctx.http, owner, repo, stars)
            ts = sample.get("timestamps") or []
            report.meta["star_sample_size"] = sample.get("sampled", 0)
            if len(ts) >= 20:
                frac = _max_window_fraction(ts, window_days=7)
                report.meta["star_burst_fraction"] = round(frac, 2)
                if frac >= 0.6:
                    reasons.append(
                        f"{int(frac * 100)}% of sampled stars landed within one week (burst)"
                    )

        if reasons:
            report.add(Finding(
                self.id, Severity.MEDIUM,
                "Possible star inflation / fake popularity",
                "Heuristic signals: " + "; ".join(reasons) + ". "
                "Star count may overstate real adoption — verify before trusting it.",
                Grade.WARN,
            ))
