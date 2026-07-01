"""Fake-star / inflated-popularity check (opt-in: ``--deep`` / deep_fake_stars).

Star counts are the #1 trust signal people use to decide whether an AI's repo
suggestion is legit — and they are routinely bought. But **normal viral growth
looks like a burst too**, so a naive "burst = suspicious" rule floods you with
false positives on official orgs and genuinely popular projects.

So after detecting a burst we require it to *co-occur with a risk factor* and we
suppress it for high-trust repos:

* **Reputable owner** (microsoft/google/github/huggingface/…) → suppressed.
* **Real adoption** (forks scale with stars) → suppressed. You can buy stars,
  but you can't buy forks / real usage — the strongest anti-fake signal.
* A burst on a **new, thin, unknown-owner** repo → ⚠️ WARN (the ECC/gbrain
  pattern). A burst on an older/established repo with no other risk → ℹ️ info,
  not a warning.

Still heuristics — never a hard ❌. Complements StarScout / Astronomer / StarGuard.
"""

from __future__ import annotations

from typing import List

from .._dates import age_days, parse_iso
from ..github import fetch_stargazers_sample
from ..models import Finding, Grade, Severity
from .base import Check, CheckContext

# Owners that don't buy stars. Lowercased logins.
_REPUTABLE_OWNERS = {
    "microsoft", "google", "googleapis", "google-research", "google-deepmind",
    "deepmind", "github", "apple", "meta", "facebook", "facebookresearch",
    "amazon", "aws", "awslabs", "nvidia", "openai", "anthropics", "anthropic",
    "huggingface", "alibaba", "tencent", "bytedance", "baidu", "cloudflare",
    "vercel", "netlify", "pytorch", "tensorflow", "kubernetes", "cncf", "apache",
    "mozilla", "gitlab", "jetbrains", "redhat", "ibm", "intel", "oracle",
    "elastic", "hashicorp", "databricks", "langchain-ai", "run-llama",
    "mistralai", "stability-ai", "cohere-ai", "salesforce", "uber", "airbnb",
    "netflix", "spotify", "shopify", "stripe", "atlassian", "grafana",
    "prometheus", "denoland", "nodejs", "rust-lang", "golang", "python",
    "pandas-dev", "numpy", "scikit-learn", "ollama", "vllm-project", "modelcontextprotocol",
}


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


def _classify(stars, forks, owner, age):
    """Decide what to do once burst/anomaly signals exist. Pure (testable).

    Returns ("suppress"|"warn"|"info", note). Reputable owners and repos with
    real adoption (forks tracking stars) are suppressed; a burst on a new, thin,
    non-major repo warns; anything else is low-confidence info.
    """
    if (owner or "").lower() in _REPUTABLE_OWNERS:
        return ("suppress", "reputable owner")
    # Forks scale with real usage; fake-star repos have almost none.
    if forks >= max(10, stars // 100):
        return ("suppress", "real adoption (forks track stars)")
    new = age is not None and age < 180
    return ("warn" if new else "info", "")


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
        age = age_days(gh.get("created_at"))

        reasons = []
        if age is not None and age < 90 and stars > 3000:
            reasons.append(f"{stars}★ on a repo only ~{int(age)} days old")
        if stars >= 1000 and forks <= max(2, stars // 1000) and forks < 5:
            reasons.append(f"{stars}★ but only {forks} fork(s)")
        if owner and repo:
            sample = fetch_stargazers_sample(ctx.http, owner, repo, stars)
            ts = sample.get("timestamps") or []
            report.meta["star_sample_size"] = sample.get("sampled", 0)
            if len(ts) >= 20:
                frac = _max_window_fraction(ts, window_days=7)
                report.meta["star_burst_fraction"] = round(frac, 2)
                if frac >= 0.6:
                    reasons.append(f"{int(frac * 100)}% of sampled stars landed within one week")

        if not reasons:
            return

        verdict, note = _classify(stars, forks, owner, age)
        if verdict == "suppress":
            report.meta["fake_stars"] = f"suppressed: {note}"
            return
        if verdict == "warn":
            report.add(Finding(
                self.id, Severity.MEDIUM,
                "Possible star inflation / fake popularity",
                "Heuristic signals: " + "; ".join(reasons) + ". New repo, few "
                "forks, non-major owner — consistent with bought stars. Verify "
                "before trusting the star count.",
                Grade.WARN,
            ))
        else:
            report.add(Finding(
                self.id, Severity.LOW,
                "Star burst, but no other risk signal",
                "Signals: " + "; ".join(reasons) + ". The repo isn't new and the "
                "owner/adoption don't fit the bought-star pattern — likely organic "
                "trending. Noted for awareness.",
                Grade.OK,
            ))
