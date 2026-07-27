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
from .license_i18n import search_restrictive

# Human-readable names for the evidence message. Telling the reader the LICENSE
# was written in Korean is half the explanation of why GitHub gave up on it.
_LANG_NAMES = {
    "ko": "Korean", "ja": "Japanese", "zh": "Chinese", "es": "Spanish",
    "pt": "Portuguese", "fr": "French", "de": "German", "it": "Italian",
    "nl": "Dutch", "pl": "Polish", "ru": "Russian", "uk": "Ukrainian",
    "tr": "Turkish", "id": "Indonesian", "vi": "Vietnamese", "th": "Thai",
    "ar": "Arabic", "hi": "Hindi", "sv": "Swedish", "cs": "Czech",
    "ro": "Romanian", "el": "Greek", "he": "Hebrew", "fa": "Persian",
}

# "Does this README talk about licensing at all?" — the gate before trusting a
# README hit. Latin "licen" misses every non-Latin script, which would have
# silently disabled the README fallback for exactly the projects this release
# is meant to serve.
_LICENSE_WORD = re.compile(
    r"licen[cs]|licenz|licencia|licença|licence|licenza|licentie|licencja|"
    r"лиценз|ліценз|lisans|lisensi|giấy phép|ใบอนุญาต|رخصة|ترخيص|लाइसेंस|"
    r"라이선스|라이센스|이용\s*약관|ライセンス|许可|許可|授权|授權|"
    r"licens|licenc|licență|άδεια|רישיון",
    re.IGNORECASE,
)


def _mentions_license(text: str) -> bool:
    return bool(text) and bool(_LICENSE_WORD.search(text))

# NOTE: multilingual restrictive-license detection lives in ``license_i18n``
# (25 languages, proximity-based). It used to be a single English-only regex
# here; keeping one source of truth avoids the two drifting apart.

# Positive identification of a standard license from the *body* of a custom /
# NOASSERTION LICENSE file. GitHub reports NOASSERTION whenever its classifier
# is unsure — including for verbatim MIT text with an unusual copyright line.
# Without this, such a repo produced no license finding at all ("repo exists"),
# so a curator had to open the file by hand to learn it was plain MIT.
_BODY_SIGNATURES = [
    (re.compile(r"permission is hereby granted, free of charge", re.I), "MIT"),
    (re.compile(r"apache license[\s,]+version 2\.0", re.I), "Apache-2.0"),
    (re.compile(r"redistribution and use in source and binary forms", re.I), "BSD"),
    (re.compile(r"mozilla public license", re.I), "MPL-2.0"),
    (re.compile(r"\bthe unlicense\b|this is free and unencumbered software", re.I), "Unlicense"),
    (re.compile(r"internet systems consortium|\bISC License\b", re.I), "ISC"),
    (re.compile(r"do what the fuck you want", re.I), "WTFPL"),
]

# Word-boundary matcher for permissive ids. A plain substring test silently
# swallowed restrictive names that merely *contain* a permissive token — e.g.
# "Li·mit·ed Commercial License" matched "mit" and was graded
# "Safe for commercial use", the worst possible direction to be wrong in.
_PERMISSIVE_RE = re.compile(
    r"(?<![a-z0-9])(?:mit|bsd|apache|isc|mpl|unlicense|0bsd|zlib|"
    r"python software foundation|psf)(?![a-z0-9])",
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

        if _PERMISSIVE_RE.search(low):
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
        """Read the raw LICENSE/README text for non-commercial restrictions.

        Two outcomes matter, and both were previously lost:

        * restrictive terms found -> the existing WARN, and
        * *no* restrictive terms but the body is recognisably a standard
          permissive license -> say so explicitly (:meth:`_identify_body`).

        Staying silent in the second case is not neutral: it reads as "unknown
        license" and pushes a curator into a manual file read for what is
        plainly MIT.
        """
        if ctx.offline:
            return None
        gh = report.meta.get("github_resolved")
        if not gh:
            return None
        from ..github import fetch_license_text, fetch_readme

        text = fetch_license_text(ctx.http, gh["owner"], gh["repo"]) or ""
        source, hit = "LICENSE", search_restrictive(text)
        if not hit:
            readme = fetch_readme(ctx.http, gh["owner"], gh["repo"]) or ""
            # Only trust the README when it actually discusses a license.
            if _mentions_license(readme):
                h2 = search_restrictive(readme)
                if h2:
                    source, hit, text = "README", h2, readme
        if not hit:
            # Nothing restrictive. Before giving up, try to name it positively
            # from the LICENSE body so the caller gets a usable answer.
            return self._identify_body(report, text)

        lang = _LANG_NAMES.get(hit.language, hit.language)
        in_lang = "" if hit.language == "en" else f" (written in {lang})"
        report.meta["license"] = f"custom/NOASSERTION (restrictive, {hit.language})"
        report.meta["license_lang"] = hit.language
        return Finding(
            self.id, Severity.HIGH,
            "License trap: custom / restrictive (non-commercial signals)",
            f"GitHub couldn't classify the license (SPDX=NOASSERTION), but the "
            f"{source}{in_lang} contains restrictive terms — likely "
            f"non-commercial / research-only, unsafe for a commercial product "
            f"without a separate license. Evidence: \"...{hit.snippet}...\"",
            Grade.WARN,
        )

    def _identify_body(self, report, text: str) -> Optional[Finding]:
        """Name a standard license from the LICENSE body when SPDX is unknown.

        Only fires on a verbatim signature phrase, so it cannot promote a
        modified or dual-licensed file by accident. Graded OK, but worded so the
        reader knows the answer came from body text rather than GitHub's
        classifier — previously this case produced no license finding at all,
        which reads as "unlicensed" and forces a manual file read.
        """
        if not text.strip():
            return None
        for pattern, label in _BODY_SIGNATURES:
            if pattern.search(text):
                report.meta["license"] = f"{label} (identified from LICENSE body)"
                return Finding(
                    self.id, Severity.INFO,
                    f"Permissive license ({label}, read from LICENSE text)",
                    "GitHub reported SPDX=NOASSERTION, but the LICENSE body is "
                    f"verbatim {label} with no restrictive terms — safe for "
                    "commercial use. Surfaced explicitly because the SPDX field "
                    "alone would have left this looking unlicensed.",
                    Grade.OK,
                )
        return None
