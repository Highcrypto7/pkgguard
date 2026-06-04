"""Turn a list of findings into a single verdict per item.

Rule of thumb: **the worst finding wins.** A package that exists and is
popular but ships under AGPL is still a ⚠️ for a commercial user; a package
that does not exist at all is ❌ no matter what else we found.

Grade ranking (see :class:`pkgguard.models.Grade`): danger > warn > unknown > ok.
We take the max-ranked ``grade_hint`` across findings. ``unknown`` sits between
``ok`` and ``warn`` so "we couldn't check X" never masquerades as a clean pass,
but also isn't treated as a risk on its own.
"""

from __future__ import annotations

from ..models import Grade, ItemReport


def finalize(report: ItemReport) -> ItemReport:
    """Compute ``report.grade`` and ``report.summary`` from its findings."""
    if not report.findings:
        report.grade = Grade.UNKNOWN
        report.summary = "No checks produced a result."
        return report

    driver = max(
        report.findings,
        key=lambda f: (f.grade_hint.rank, f.severity.rank),
    )
    report.grade = driver.grade_hint

    if report.grade is Grade.OK:
        # Lead with the positive existence confirmation, not a minor caveat.
        existence = next((f for f in report.findings if f.check == "existence"), None)
        report.summary = (existence or driver).title
    else:
        report.summary = driver.title
    return report
