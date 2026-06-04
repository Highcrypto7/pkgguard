"""Base types for checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..http import HttpClient
from ..models import ItemReport


@dataclass
class CheckContext:
    """Shared configuration + clients passed to every check."""

    http: HttpClient
    offline: bool = False
    # Run the expensive fake-star analysis (extra GitHub API calls). Opt-in.
    deep_fake_stars: bool = False
    # Download the package archive and statically scan its source. Opt-in.
    deep_source: bool = False
    # Thresholds (kept here so they're easy to tune / override).
    typosquat_min_ratio: float = 0.82   # similarity above which we warn
    stale_days_warn: int = 365          # no commits in this long -> stale
    stale_days_danger: int = 365 * 2    # ... this long -> likely abandoned
    new_package_days: int = 90          # newer than this -> "freshly registered"

    # populated lazily by checks that load data files
    _resources: dict = field(default_factory=dict)


class Check:
    """A single verification axis.

    Subclasses implement :meth:`run`, appending :class:`Finding` objects to the
    report and stashing reusable data in ``report.meta``. ``applies`` lets a
    check skip items it doesn't handle (e.g. a PyPI-only check skips npm items).
    """

    #: stable identifier, used in Finding.check and JSON output
    id: str = "base"

    def applies(self, report: ItemReport, ctx: CheckContext) -> bool:
        return True

    def run(self, report: ItemReport, ctx: CheckContext) -> None:  # pragma: no cover
        raise NotImplementedError

    def safe_run(self, report: ItemReport, ctx: CheckContext) -> None:
        """Run the check, swallowing unexpected errors.

        A bug or transient failure in one check must never abort the whole
        report. Failures are recorded in meta for debugging but do not crash.
        """
        if not self.applies(report, ctx):
            return
        try:
            self.run(report, ctx)
        except Exception as e:  # defensive: keep other checks running
            report.meta.setdefault("_check_errors", {})[self.id] = repr(e)
