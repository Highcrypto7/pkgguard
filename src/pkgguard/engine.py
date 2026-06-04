"""Orchestration: parse -> run checks -> aggregate into a Report."""

from __future__ import annotations

import os
from typing import List, Optional

from .checks import Check, CheckContext, build_checks
from .http import HttpClient
from .models import Item, ItemReport, Report
from .parse import parse_input
from .report import finalize


def _github_token() -> Optional[str]:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or None


def vet_items(
    items: List[Item],
    offline: bool = False,
    timeout: float = 8.0,
    deep_fake_stars: bool = False,
    deep_source: bool = False,
    github_token: Optional[str] = None,
    use_cache: bool = True,
    cache_ttl: float = 24 * 3600,
    checks: Optional[List[Check]] = None,
) -> Report:
    """Run the check pipeline over already-parsed items."""
    disk = None
    if use_cache:
        try:
            from .cache import DiskCache
            disk = DiskCache(ttl=cache_ttl)
        except Exception:
            disk = None

    http = HttpClient(
        timeout=timeout,
        offline=offline,
        github_token=github_token or _github_token(),
        cache=disk,
    )
    ctx = CheckContext(http=http, offline=offline, deep_fake_stars=deep_fake_stars,
                       deep_source=deep_source)
    pipeline = checks if checks is not None else build_checks()

    report = Report()
    try:
        for item in items:
            ir = ItemReport(item=item)
            for check in pipeline:
                check.safe_run(ir, ctx)
            finalize(ir)
            report.items.append(ir)
    finally:
        http.flush()
    return report


def vet(
    text: str,
    fmt: str = "auto",
    ecosystem: Optional[str] = None,
    source: str = "input",
    **kwargs,
) -> Report:
    """Parse ``text`` and vet every package/repo reference found."""
    items = parse_input(text, source=source, fmt=fmt, ecosystem=ecosystem)
    return vet_items(items, **kwargs)
