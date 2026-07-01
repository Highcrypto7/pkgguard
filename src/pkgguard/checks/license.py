"""License-trap check.

Most supply-chain scanners ignore licensing entirely. But for anyone shipping
a commercial product, the license an AI casually recommended can be a landmine:
AGPL/SSPL/BUSL force source disclosure or block SaaS use, CC-BY-NC bans
commercial use outright, and "no license at all" means *all rights reserved* —
you legally cannot reuse it. We surface these explicitly.

Grades here are about commercial/legal risk, not security: traps are ⚠️ (you
*can* use them, but read the terms), unknown/missing is a softer ⚠️.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from ..models import Ecosystem, Finding, Grade, Severity
from .base import Check, CheckContext

# Restrictive terms found in the raw text of custom / NOASSERTION licenses that
# GitHub can't map to a standard SPDX id (common for AI model-weight repos).
_RESTRICTIVE = re.compile(
    r"non[- ]?commercial|not for commercial|may not be used commercially|"
    r"commercial use (?:requires|is not permitted|is prohibited|prohibited)|"
    r"requires a separate (?:commercial )?license|separate commercial license|"
    r"research (?:only|purposes|use only)|for research purposes|evaluation only|"
    r"no redistribution|cc[- ]by[- ]nc|responsible ai license|\bRAIL\b|"
    r"academic (?:use )?only|personal use only",
    re.IGNORECASE,
)

# Ecosystems whose registry response reliably carries license info, so an empty
# license genuinely means "none declared" rather than "not fetched".
_LICENSE_BEARING = {
    Ecosystem.PYPI, Ecosystem.NPM, Ecosystem.CRATES, Ecosystem.RUBYGEMS,
    Ecosystem.PACKAGIST,
}

# substring (lowercased) -> (short label, human note)
_TRAPS = [
    ("agpl", ("AGPL", "Network copyleft: using it in a hosted service can force you to open-source your whole app.")),
    ("sspl", ("SSPL", "Server Side Public License: hostile to SaaS/commercial hosting; not OSI-approved.")),
    ("business source", ("BUSL", "Business Source License: source-available but use is restricted until a change date.")),
    ("busl", ("BUSL", "Business Source License: use restricted until the change date.")),
    ("commons clause", ("Commons Clause", "Adds a 'no selling' restriction on top of an OSS license.")),
    ("elastic license", ("Elastic License", "Source-available; restricts managed-service / SaaS use.")),
    ("functional source", ("FSL", "Functional Source License: time-limited commercial restriction.")),
    ("non-commercial", ("Non-Commercial", "Commercial use is prohibited.")),
    ("noncommercial", ("Non-Commercial", "Commercial use is prohibited.")),
    ("cc-by-nc", ("CC-BY-NC", "Creative Commons Non-Commercial: cannot be used in commercial products.")),
    ("cc by-nc", ("CC-BY-NC", "Creative Commons Non-Commercial: cannot be used in commercial products.")),
    ("fair-code", ("fair-code", "Source-available but not OSS; commercial use limited (e.g. n8n Sustainable Use License).")),
    ("sustainable use", ("Sustainable Use", "Source-available; commercial/SaaS use restricted.")),
    ("prosperity", ("Prosperity", "Non-commercial for a trial period.")),
    ("rpl", ("RPL", "Reciprocal Public License: strong copyleft, even for internal/SaaS use.")),
]

# Copyleft that is fine for OSS but a trap for closed/commercial distribution.
_WEAK_COPYLEFT = [
    ("gpl-3", "GPL-3.0"),
    ("gpl-2", "GPL-2.0"),
    ("gplv3", "GPL-3.0"),
    ("gplv2", "GPL-2.0"),
    ("gnu general public", "GPL"),
]

_PERMISSIVE = ("mit", "bsd", "apache", "isc", "mpl", "unlicense", "0bsd", "zlib", "python software foundation", "psf")
_NO_LICENSE = ("", "unlicensed", "unknown", "noassertion", "other", "proprietary", "see license")


def _license_text(report) -> Tuple[str, str]:
    """Return (raw_license, source) from registry or github metadata."""
    reg = report.meta.get("registry") or {}
    if reg.get("license"):
        return str(reg["license"]), "registry"
    gh = report.meta.get("github") or {}
    if gh.get("license_spdx") and gh["license_spdx"] not in ("NOASSERTION", ""):
        return str(gh["license_spdx"]), "github"
    if gh.get("license_name"):
        return str(gh["license_name"]), "github"
    return "", "none"


class LicenseCheck(Check):
    id = "license"

    def run(self, report, ctx: CheckContext) -> None:
        # Only meaningful once we know the package exists.
        if report.meta.get("registry") is None and not report.meta.get("github"):
            return
        raw, src = _license_text(report)
        low = raw.lower().strip()
        report.meta["license"] = raw

        for needle, (label, note) in _TRAPS:
            if needle in low:
                report.add(Finding(
                    self.id, Severity.HIGH,
                    f"License trap: {label}",
                    f"{note} (declared license: '{raw}', via {src})",
                    Grade.WARN,
                ))
                return

        for needle, label in _WEAK_COPYLEFT:
            if needle in low:
                report.add(Finding(
                    self.id, Severity.MEDIUM,
                    f"Copyleft license: {label}",
                    "Fine for open source, but distributing it inside a closed-source "
                    "product triggers source-disclosure obligations.",
                    Grade.WARN,
                ))
                return

        if any(p in low for p in _PERMISSIVE):
            report.add(Finding(
                self.id, Severity.INFO, f"Permissive license ({raw})",
                "Safe for commercial use.", Grade.OK,
            ))
            return

        # Custom / NOASSERTION fallback: GitHub couldn't map this to a standard
        # SPDX id, so read the actual LICENSE (and README) text and look for
        # non-commercial / research-only restrictions.
        custom = self._scan_custom_license(report, ctx)
        if custom is not None:
            report.add(custom)
            return

        if low in _NO_LICENSE:
            # Only assert "no license == all rights reserved" for ecosystems whose
            # registry actually reports license metadata. For others (NuGet/Pub/Go
            # lightweight endpoints), absence means "not reported", not "none".
            if report.item.ecosystem in _LICENSE_BEARING:
                report.add(Finding(
                    self.id, Severity.MEDIUM, "No clear license",
                    "No license == all rights reserved: you have no legal right to "
                    "reuse, modify or redistribute it. Confirm before depending on it.",
                    Grade.WARN,
                ))
            else:
                report.add(Finding(
                    self.id, Severity.LOW, "License not reported",
                    "This registry doesn't expose license metadata here; check the "
                    "package page or repository for its license.",
                    Grade.OK,
                ))
            return

        # Unrecognized but present — note it without dragging down the verdict.
        # The package exists; we just can't auto-classify the license string.
        report.add(Finding(
            self.id, Severity.LOW, f"Unrecognized license ({raw})",
            "Could not classify automatically — review the terms manually if "
            "you need a specific license posture.",
            Grade.OK,
        ))

    def _scan_custom_license(self, report, ctx: CheckContext) -> Optional[Finding]:
        """Read the raw LICENSE/README text for non-commercial restrictions."""
        if ctx.offline:
            return None
        gh = report.meta.get("github_resolved")
        if not gh:
            return None
        from ..github import fetch_license_text, fetch_readme

        text = fetch_license_text(ctx.http, gh["owner"], gh["repo"]) or ""
        source, match = "LICENSE", _RESTRICTIVE.search(text)
        if not match:
            readme = fetch_readme(ctx.http, gh["owner"], gh["repo"]) or ""
            # Only trust the README when it actually discusses a license.
            if "licen" in readme.lower():
                m2 = _RESTRICTIVE.search(readme)
                if m2:
                    source, match, text = "README", m2, readme
        if not match:
            return None

        start = max(0, match.start() - 30)
        snippet = " ".join(text[start:match.end() + 50].split())[:110]
        report.meta["license"] = "custom/NOASSERTION (restrictive)"
        return Finding(
            self.id, Severity.HIGH,
            "License trap: custom / restrictive (non-commercial signals)",
            f"GitHub couldn't classify the license (SPDX=NOASSERTION), but the "
            f"{source} contains restrictive terms — likely non-commercial / "
            f"research-only, unsafe for a commercial product without a separate "
            f"license. Evidence: \"...{snippet}...\"",
            Grade.WARN,
        )
