"""pkgguard — vet the packages and repos your AI assistant recommended.

Catches hallucinated / slopsquatted names, malware signals, license traps,
dead repos, and fake-star inflation, then prints a per-item trust report.

Public API:
    from pkgguard import vet
    report = vet("requests\\nnumpy\\npandas")
"""

from __future__ import annotations

__version__ = "0.1.0"

from .models import (  # noqa: E402
    Ecosystem,
    Finding,
    Grade,
    Item,
    ItemReport,
    Report,
    Severity,
)

__all__ = [
    "__version__",
    "Ecosystem",
    "Finding",
    "Grade",
    "Item",
    "ItemReport",
    "Report",
    "Severity",
    "vet",
]


def vet(text: str, **kwargs):
    """Convenience entry point: parse ``text`` and return a :class:`Report`.

    Imported lazily so that ``import pkgguard`` stays cheap and free of
    network-related imports until actually used.
    """
    from .engine import vet as _vet

    return _vet(text, **kwargs)
