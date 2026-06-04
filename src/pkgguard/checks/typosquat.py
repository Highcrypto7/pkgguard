"""Typosquat / slopsquat similarity check.

Compares the item name against a curated list of popular packages for its
ecosystem. A name that is one or two edits away from a high-traffic package —
but is *not* that package — is the classic typosquat (``requets``) or
slopsquat (an AI-plausible near-miss) bait.

We record a ``typosquat_match`` in ``report.meta`` so the malware check can
escalate "freshly-registered look-alike" to a stronger verdict.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional, Tuple

from ..models import Ecosystem, Finding, Grade, Severity
from ..parse.normalize import normalize_npm, normalize_pypi
from .base import Check, CheckContext


@lru_cache(maxsize=None)
def _load(resource: str) -> Tuple[str, ...]:
    try:
        from importlib.resources import files
        text = (files("pkgguard.data") / resource).read_text(encoding="utf-8")
    except Exception:
        return ()
    names = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            names.append(line.lower())
    return tuple(names)


def _levenshtein(a: str, b: str, cap: int = 3) -> int:
    """Bounded Levenshtein distance; returns cap+1 if it exceeds ``cap``."""
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if abs(la - lb) > cap:
        return cap + 1
    prev = list(range(lb + 1))
    for i in range(1, la + 1):
        cur = [i] + [0] * lb
        best = cur[0]
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            best = min(best, cur[j])
        if best > cap:
            return cap + 1
        prev = cur
    return prev[lb]


def _canonical(name: str) -> str:
    """Collapse separators so requests/requesocks-style tricks line up."""
    return name.replace("-", "").replace("_", "").replace(".", "")


# Digit/symbol -> letter confusables, for catching homoglyph squats like
# "dj4ng0" -> "django" or "reque5t5" -> "requests" that exceed an edit cap.
_HOMOGLYPH = str.maketrans(
    {"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b",
     "9": "g", "$": "s", "@": "a", "|": "l"}
)


def _fold(name: str) -> str:
    return _canonical(name).translate(_HOMOGLYPH)


def _closest(name: str, popular: Tuple[str, ...]) -> Optional[Tuple[str, int]]:
    """Return (popular_name, distance) for the nearest look-alike, or None."""
    canon = _canonical(name)
    folded = _fold(name)
    has_confusable = folded != canon  # name contains digits/symbols
    best: Optional[Tuple[str, int]] = None
    for pop in popular:
        if pop == name:
            return (pop, 0)  # it *is* the popular package
        # separator-only difference (requests vs requ_ests) is highly suspicious
        if _canonical(pop) == canon and pop != name:
            return (pop, 1)
        # homoglyph fold: digit/symbol substitutions that spell a popular name
        if has_confusable and _fold(pop) == folded and pop != name:
            return (pop, 1)
        # length-aware edit distance; short names need a tighter bound
        cap = 1 if min(len(name), len(pop)) <= 5 else 2
        d = _levenshtein(name, pop, cap=cap)
        if d <= cap and (best is None or d < best[1]):
            best = (pop, d)
    return best


class TyposquatCheck(Check):
    id = "typosquat"

    def applies(self, report, ctx: CheckContext) -> bool:
        return report.item.ecosystem in (
            Ecosystem.PYPI, Ecosystem.NPM, Ecosystem.UNKNOWN,
        )

    def run(self, report, ctx: CheckContext) -> None:
        item = report.item
        if item.ecosystem is Ecosystem.NPM:
            name = normalize_npm(item.name)
            popular = _load("popular_npm.txt")
            eco_label = "npm"
        else:
            # PyPI or still-UNKNOWN (compare against PyPI list as best guess)
            name = normalize_pypi(item.name)
            popular = _load("popular_pypi.txt")
            eco_label = "PyPI"
        if not popular:
            return

        match = _closest(name, popular)
        if match is None:
            return
        pop, dist = match
        if dist == 0:
            return  # the item is itself a popular package — fine

        report.meta["typosquat_match"] = {"target": pop, "distance": dist}
        exists = report.meta.get("exists")  # True / False / None (unknown)
        if exists is False:
            # Confirmed absent but mimics a popular name -> prime slopsquat bait.
            report.add(Finding(
                self.id, Severity.HIGH,
                f"Resembles popular '{pop}' but does not exist — slopsquat bait",
                f"Only {dist} edit(s) from '{pop}'. Hallucinated near-misses like "
                f"this are exactly what attackers pre-register. Use '{pop}'.",
                Grade.DANGER,
            ))
        elif exists is True:
            # It resolves AND looks like a popular package -> possible impostor.
            report.add(Finding(
                self.id, Severity.HIGH,
                f"Look-alike of popular {eco_label} package '{pop}'",
                f"Name is {dist} edit(s) from '{pop}'. If you meant '{pop}', "
                f"install that exact name; confirm this is not an impostor.",
                Grade.WARN,
            ))
        else:
            # Couldn't verify existence (offline/rate-limited) — don't claim it's
            # absent; just warn it looks like a popular package.
            report.add(Finding(
                self.id, Severity.MEDIUM,
                f"Resembles popular '{pop}' — could not verify existence",
                f"Name is {dist} edit(s) from '{pop}'. Existence unconfirmed; make "
                f"sure this isn't a typo for '{pop}'.",
                Grade.WARN,
            ))
