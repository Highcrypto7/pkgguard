"""Core data contract for pkgguard.

Everything in pkgguard flows through these types:

    raw text --(parse)--> [Item] --(checks)--> [Finding] --(aggregate)--> ItemReport
                                                                            |
                                                              many --> Report --(render)

Keeping this module dependency-free (stdlib only) means parsers, checks and
renderers can all import it without creating import cycles.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class Ecosystem(str, Enum):
    """Where an item is expected to live."""

    PYPI = "pypi"
    NPM = "npm"
    CRATES = "crates"
    GO = "go"
    RUBYGEMS = "rubygems"
    PACKAGIST = "packagist"
    NUGET = "nuget"
    PUB = "pub"
    GITHUB = "github"
    UNKNOWN = "unknown"

    def __str__(self) -> str:  # nicer rendering
        return self.value


class Severity(str, Enum):
    """How alarming a single finding is, independent of the final grade."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        return {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}[self.value]


class Grade(str, Enum):
    """The verdict shown to the user, matching the ✅ ⚠️ ❌ mental model."""

    OK = "ok"            # ✅ looks safe to use
    WARN = "warn"        # ⚠️ usable but check the noted caveats
    DANGER = "danger"    # ❌ do not install / strong risk
    UNKNOWN = "unknown"  # ❔ could not determine (e.g. offline, rate-limited)

    @property
    def rank(self) -> int:
        # Higher = worse. UNKNOWN sits between OK and WARN: notable but not a risk.
        return {"ok": 0, "unknown": 1, "warn": 2, "danger": 3}[self.value]

    @property
    def emoji(self) -> str:
        return {"ok": "✅", "warn": "⚠️", "danger": "❌", "unknown": "❔"}[self.value]

    @property
    def label(self) -> str:
        return {
            "ok": "OK",
            "warn": "WARN",
            "danger": "DANGER",
            "unknown": "UNKNOWN",
        }[self.value]


@dataclass
class Item:
    """A single package/repo reference extracted from the input."""

    raw: str
    name: str
    ecosystem: Ecosystem = Ecosystem.UNKNOWN
    version: Optional[str] = None
    repo_url: Optional[str] = None  # set when the input was a GitHub URL/slug
    source: str = ""                # e.g. "requirements.txt", "chat-text"

    def key(self) -> str:
        return f"{self.ecosystem}:{self.name.lower()}"


@dataclass
class Finding:
    """One observation produced by a check."""

    check: str            # check id, e.g. "existence"
    severity: Severity
    title: str
    detail: str = ""
    # Which grade this finding argues for. The aggregator takes the worst.
    grade_hint: Grade = Grade.WARN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity.value,
            "title": self.title,
            "detail": self.detail,
            "grade_hint": self.grade_hint.value,
        }


@dataclass
class ItemReport:
    """All findings + metadata + final verdict for one item."""

    item: Item
    findings: List[Finding] = field(default_factory=list)
    grade: Grade = Grade.UNKNOWN
    summary: str = ""
    # Free-form metadata gathered by checks (stars, license, downloads, ...).
    # Checks read/write this so later checks can reuse earlier lookups.
    meta: Dict[str, Any] = field(default_factory=dict)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def worst(self) -> Optional[Finding]:
        if not self.findings:
            return None
        return max(self.findings, key=lambda f: (f.grade_hint.rank, f.severity.rank))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.item.name,
            "ecosystem": str(self.item.ecosystem),
            "version": self.item.version,
            "repo_url": self.item.repo_url,
            "source": self.item.source,
            "grade": self.grade.value,
            "summary": self.summary,
            "findings": [f.to_dict() for f in self.findings],
            "meta": self.meta,
        }


@dataclass
class Report:
    """The full result of a vet run."""

    items: List[ItemReport] = field(default_factory=list)

    def counts(self) -> Dict[str, int]:
        out = {g.value: 0 for g in Grade}
        for ir in self.items:
            out[ir.grade.value] += 1
        return out

    @property
    def has_danger(self) -> bool:
        return any(ir.grade is Grade.DANGER for ir in self.items)

    @property
    def has_warn(self) -> bool:
        return any(ir.grade is Grade.WARN for ir in self.items)

    def exit_code(self) -> int:
        """Process exit code, useful in CI / pre-commit hooks.

        2 = at least one DANGER, 1 = at least one WARN, 0 = all clear.
        """
        if self.has_danger:
            return 2
        if self.has_warn:
            return 1
        return 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.counts(),
            "items": [ir.to_dict() for ir in self.items],
        }
