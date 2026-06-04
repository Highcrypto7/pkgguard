"""Human-friendly terminal renderer.

Uses ``rich`` for a colourful table when it's installed, and degrades to clean
plain text otherwise (rich is an optional extra, not a hard dependency). Emoji
are swapped for ASCII tags on terminals that can't encode them (e.g. legacy
Windows code pages) so output never crashes with a UnicodeEncodeError.
"""

from __future__ import annotations

import sys
from typing import List

from ..models import Grade, ItemReport, Report

_ORDER = {Grade.DANGER: 0, Grade.WARN: 1, Grade.UNKNOWN: 2, Grade.OK: 3}

_ASCII_TAG = {
    Grade.OK: "[ OK ]",
    Grade.WARN: "[WARN]",
    Grade.DANGER: "[ !! ]",
    Grade.UNKNOWN: "[ ?? ]",
}
_ANSI = {
    Grade.OK: "\033[32m",       # green
    Grade.WARN: "\033[33m",     # yellow
    Grade.DANGER: "\033[31m",   # red
    Grade.UNKNOWN: "\033[90m",  # grey
}
_RESET = "\033[0m"
_RICH_STYLE = {
    Grade.OK: "green",
    Grade.WARN: "yellow",
    Grade.DANGER: "bold red",
    Grade.UNKNOWN: "dim",
}


def _supports_unicode(stream) -> bool:
    enc = getattr(stream, "encoding", None) or ""
    try:
        "✅⚠️❌❔".encode(enc)
        return True
    except (UnicodeEncodeError, LookupError, TypeError):
        return False


def _tag(grade: Grade, unicode_ok: bool) -> str:
    return f"{grade.emoji} {grade.label}" if unicode_ok else _ASCII_TAG[grade]


def _sorted(report: Report) -> List[ItemReport]:
    return sorted(report.items, key=lambda r: (_ORDER[r.grade], r.item.name.lower()))


def render_cli(report: Report, use_color: bool = True, stream=None) -> None:
    stream = stream or sys.stdout
    unicode_ok = _supports_unicode(stream)
    if use_color and _try_rich(report, unicode_ok, stream):
        return
    _render_plain(report, use_color, unicode_ok, stream)


def _try_rich(report: Report, unicode_ok: bool, stream) -> bool:
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.text import Text
    except Exception:
        return False
    if not stream.isatty():
        return False  # plain text is friendlier for pipes/CI logs

    console = Console(file=stream)
    table = Table(show_lines=False, expand=False)
    table.add_column("Verdict")
    table.add_column("Item", overflow="fold")
    table.add_column("Eco")
    table.add_column("Summary", overflow="fold")
    for ir in _sorted(report):
        style = _RICH_STYLE[ir.grade]
        table.add_row(
            Text(_tag(ir.grade, unicode_ok), style=style),
            Text(ir.item.name),
            Text(str(ir.item.ecosystem)),
            Text(ir.summary or ""),
        )
    console.print(table)
    _print_details_rich(report, console, unicode_ok)
    _print_footer_rich(report, console)
    return True


def _print_details_rich(report, console, unicode_ok) -> None:
    flagged = [ir for ir in _sorted(report) if ir.grade is not Grade.OK]
    if not flagged:
        return
    console.print()
    for ir in flagged:
        style = _RICH_STYLE[ir.grade]
        console.print(
            f"[{style}]{_tag(ir.grade, unicode_ok)}[/] "
            f"[bold]{ir.item.name}[/] ({ir.item.ecosystem})"
        )
        for f in ir.findings:
            if f.grade_hint is Grade.OK:
                continue
            console.print(f"    - ({f.severity.value}) {f.title}")
            if f.detail:
                console.print(f"      [dim]{f.detail}[/]")


def _print_footer_rich(report, console) -> None:
    c = report.counts()
    console.print()
    console.print(
        f"[green]{c['ok']} ok[/]  [yellow]{c['warn']} warn[/]  "
        f"[bold red]{c['danger']} danger[/]  [dim]{c['unknown']} unknown[/]"
    )


def _render_plain(report: Report, use_color: bool, unicode_ok: bool, stream) -> None:
    color = use_color and getattr(stream, "isatty", lambda: False)()

    def w(line: str = "") -> None:
        stream.write(line + "\n")

    name_w = max([len(ir.item.name) for ir in report.items] + [4]) if report.items else 4
    name_w = min(name_w, 48)
    for ir in _sorted(report):
        tag = _tag(ir.grade, unicode_ok)
        if color:
            tag = f"{_ANSI[ir.grade]}{tag}{_RESET}"
        w(f"{tag:>12}  {ir.item.name:<{name_w}}  {ir.summary}")

    # Details for non-OK items.
    flagged = [ir for ir in _sorted(report) if ir.grade is not Grade.OK]
    if flagged:
        w()
        for ir in flagged:
            w(f"{_tag(ir.grade, unicode_ok)} {ir.item.name} ({ir.item.ecosystem})")
            for f in ir.findings:
                if f.grade_hint is Grade.OK:
                    continue
                w(f"    - ({f.severity.value}) {f.title}")
                if f.detail:
                    w(f"      {f.detail}")
            w()

    c = report.counts()
    w(f"{c['ok']} ok  {c['warn']} warn  {c['danger']} danger  {c['unknown']} unknown")
