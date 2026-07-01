"""Purpose / policy check (opt-in: ``--policy``).

pkgguard's core checks ask "is this dependency safe to *install*". This is a
different lens: "is the tool's **purpose** abuse or attack?" — e.g. bulk account
farms with SMS/CAPTCHA-bypass, DDoS stressers, credential stuffers. Metadata and
even a source scan can look clean while the whole point of the repo is ToS abuse.

This is a **fuzzy heuristic, not a supply-chain signal**, and it is off by
default. It fires only on *multiple* abuse signals in an *automation* context,
and it backs off when the repo reads as defensive/educational (pentest, blue
team, detection, research). Treat any hit as "a human should look", not proof.
"""

from __future__ import annotations

import re
from typing import List

from ..models import Finding, Grade, Severity
from .base import Check, CheckContext

# High-signal attack tooling.
_ATTACK = re.compile(
    r"\b(ddos|stresser|booter|credential stuffing|password spray(?:ing)?|"
    r"account cracker|account checker|combo list|token stealer|rat builder)\b",
    re.IGNORECASE,
)
# Account-farming / verification-bypass tooling.
_FARM = re.compile(
    r"(mass account|bulk account|account generator|account creator|"
    r"verification bypass|2fa bypass|otp bypass|sms verification bypass|"
    r"captcha bypass|phone verification bypass|anti[- ]detect|\b5sim\b|"
    r"sms.?activate|fake account (?:generator|creator)|mass (?:dm|follow))",
    re.IGNORECASE,
)
# Automation context that turns "mentions X" into "does X at scale".
_AUTOMATION = re.compile(
    r"\b(auto(?:mat\w*)?|bulk|mass|generat\w*|creat\w*|bots?|farm\w*|unlimited|"
    r"batch|at scale|scal\w*)\b",
    re.IGNORECASE,
)
# STRUCTURAL defensive context that suppresses a naive hit. Deliberately does
# NOT include weak "for educational purposes only" / "authorized use" cover text,
# which abuse tools routinely bolt on as a fig leaf.
_DEFENSE = re.compile(
    r"(detection rule|blue team|honeypot|\bsiem\b|incident response|"
    r"threat intel\w*|forensic\w*|intrusion detection|for defenders|"
    r"malware analysis|detect(?:ing|ion) (?:and|of) (?:attacks|threats)|"
    r"mitigat\w+ (?:attacks|threats)|protect against)",
    re.IGNORECASE,
)


class PolicyCheck(Check):
    id = "policy"

    def applies(self, report, ctx: CheckContext) -> bool:
        return (
            getattr(ctx, "policy", False)
            and not ctx.offline
            and bool(report.meta.get("github_resolved") or report.meta.get("registry"))
        )

    def run(self, report, ctx: CheckContext) -> None:
        parts = []
        gh = report.meta.get("github") or {}
        parts.append(gh.get("description") or "")
        reg = report.meta.get("registry") or {}
        parts.append(reg.get("summary") or "")
        gh_resolved = report.meta.get("github_resolved")
        if gh_resolved:
            from ..github import fetch_readme
            parts.append(fetch_readme(ctx.http, gh_resolved["owner"], gh_resolved["repo"]) or "")
        text = "\n".join(p for p in parts if p)
        if not text.strip():
            return

        attack = _uniq(_ATTACK.findall(text))
        farm = _uniq([m if isinstance(m, str) else m[0] for m in _FARM.findall(text)])
        signals = attack + farm
        if not signals:
            return

        automation = bool(_AUTOMATION.search(text))
        defense_hits = len(_DEFENSE.findall(text))

        # Require corroboration: 2+ distinct signals, or a strong attack term
        # plus an automation context. A single passing mention isn't enough.
        strong = bool(attack)
        if not (len(signals) >= 2 or (strong and automation)):
            return

        # Back off when the repo is structurally defensive (detection/blue-team/
        # forensics), not when it merely bolts on an "educational purposes" cover.
        if defense_hits >= 2:
            report.meta["policy"] = f"suppressed: defensive context ({defense_hits} signals)"
            return

        evidence = ", ".join(f'"{s}"' for s in signals[:5])
        danger = (strong or (farm and automation))
        grade = Grade.DANGER if danger else Grade.WARN
        report.meta["policy"] = {"signals": signals, "automation": automation}
        report.add(Finding(
            self.id, Severity.HIGH if danger else Severity.MEDIUM,
            "Policy: likely ToS-abuse / attack tool",
            f"Purpose signals: {evidence}"
            + (" (automation context)" if automation else "")
            + ". This is a policy heuristic about the tool's *purpose*, not a "
            "supply-chain signal — confirm with human judgment before acting.",
            grade,
        ))


def _uniq(items: List[str]) -> List[str]:
    seen, out = set(), []
    for it in items:
        k = it.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(it.lower().strip())
    return out
