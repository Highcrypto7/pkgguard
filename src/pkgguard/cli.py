"""``pkgguard`` command-line interface.

Examples
--------
    pkgguard requests numpy pandas              # vet a few names
    pkgguard -f requirements.txt                # vet a manifest
    pkgguard -f package.json
    pbpaste | pkgguard --stdin                  # vet whatever ChatGPT told you
    pkgguard --stdin < chatlog.txt --json       # machine-readable output
    pkgguard -f requirements.txt --fail-on warn # gate a CI job / pre-commit hook
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

from . import __version__
from .engine import vet_items
from .models import Item, Report
from .parse import parse_input
from .report import render_cli, render_json, render_md


def _setup_console() -> None:
    """Make stdout/stderr UTF-8 where possible (avoids cp949 emoji crashes)."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfig = getattr(stream, "reconfigure", None)
        if reconfig:
            try:
                reconfig(encoding="utf-8", errors="replace")
            except Exception:
                pass


def _infer_format(path: str) -> str:
    base = os.path.basename(path).lower()
    if base == "package.json":
        return "package-json"
    if base.startswith("requirements") and base.endswith(".txt"):
        return "requirements"
    if base.endswith(".json"):
        return "package-json"
    if base == "cargo.toml":
        return "cargo"
    if base == "gemfile":
        return "gemfile"
    if base == "go.mod":
        return "go-mod"
    return "auto"


def _read_file(path: str, parser, fmt: str, ecosystem) -> List[Item]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError as e:
        parser.error(f"could not read {path}: {e}")
    use_fmt = fmt if fmt != "auto" else _infer_format(path)
    return parse_input(text, source=os.path.basename(path), fmt=use_fmt, ecosystem=ecosystem)


def _dedupe(items: List[Item]) -> List[Item]:
    seen, out = set(), []
    for it in items:
        if it.key() not in seen:
            seen.add(it.key())
            out.append(it)
    return out


def _collect_items(args, parser, ecosystem) -> List[Item]:
    """Build the item list from files / stdin / positional names.

    Positional args that are existing files are read as files (so both
    `pkgguard requirements.txt` and pre-commit's filename passing just work).
    """
    items: List[Item] = []

    if args.file:
        items += _read_file(args.file, parser, args.format, ecosystem)

    file_positionals = [n for n in args.names if os.path.isfile(n)]
    if file_positionals and len(file_positionals) == len(args.names):
        for path in args.names:
            items += _read_file(path, parser, args.format, ecosystem)
    elif args.stdin or (not args.names and not args.file and not sys.stdin.isatty()):
        text = sys.stdin.read()
        items += parse_input(text, source="stdin", fmt=args.format, ecosystem=ecosystem)
    elif args.names:
        if len(args.names) == 1 and ("\n" in args.names[0] or args.format != "auto"):
            items += parse_input(args.names[0], source="args", fmt=args.format, ecosystem=ecosystem)
        else:
            fmt = args.format if args.format != "auto" else "list"
            items += parse_input("\n".join(args.names), source="args", fmt=fmt, ecosystem=ecosystem)
    elif not args.file:
        parser.error("no input: pass names/files, -f FILE, or pipe text with --stdin")

    return _dedupe(items)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pkgguard",
        description="Vet the packages and repos your AI assistant recommended "
        "before you install them — catches hallucinated/slopsquatted names, "
        "malware signals, license traps, dead repos and fake-star inflation.",
    )
    p.add_argument("names", nargs="*", help="package/repo names to vet")
    p.add_argument("-f", "--file", help="read input from a file "
                   "(requirements.txt, package.json, or any text)")
    p.add_argument("--stdin", action="store_true", help="read input from stdin")
    p.add_argument(
        "--format", default="auto",
        choices=["auto", "requirements", "package-json", "cargo", "gemfile",
                 "go-mod", "chat", "list"],
        help="how to parse the input (default: auto-detect)",
    )
    p.add_argument("-e", "--ecosystem",
                   choices=["pypi", "npm", "crates", "go", "rubygems",
                            "packagist", "nuget", "pub"],
                   help="assumed ecosystem for bare names")
    p.add_argument("--pypi", action="store_true", help="shortcut for -e pypi")
    p.add_argument("--npm", action="store_true", help="shortcut for -e npm")
    p.add_argument("--offline", action="store_true",
                   help="do no network calls (most checks become ❔ unknown)")
    p.add_argument("--deep", action="store_true",
                   help="enable extra fake-star analysis (more GitHub API calls)")
    p.add_argument("--scan", action="store_true",
                   help="download package archives and statically scan their "
                        "source for malware signals (no code is executed)")
    p.add_argument("--policy", action="store_true",
                   help="flag tools whose *purpose* looks like ToS-abuse/attack "
                        "(account farms, bypass, DDoS). Heuristic, not supply-chain.")
    p.add_argument("--timeout", type=float, default=8.0,
                   help="per-request timeout in seconds (default: 8)")
    p.add_argument("--json", action="store_true", help="output JSON")
    p.add_argument("--markdown", "--md", action="store_true", dest="markdown",
                   help="output Markdown")
    p.add_argument("-o", "--output", help="write the report to a file")
    p.add_argument("--no-color", action="store_true", help="disable colour")
    p.add_argument(
        "--fail-on", default="danger", choices=["danger", "warn", "never"],
        help="exit non-zero when the worst verdict reaches this level "
        "(default: danger)",
    )
    p.add_argument("--no-cache", action="store_true",
                   help="disable the on-disk response cache")
    p.add_argument("--cache-ttl", type=float, default=24 * 3600,
                   help="cache freshness in seconds (default: 86400)")
    p.add_argument("--clear-cache", action="store_true",
                   help="clear the on-disk cache and exit")
    p.add_argument("-V", "--version", action="version",
                   version=f"pkgguard {__version__}")
    return p


def _exit_code(report: Report, fail_on: str) -> int:
    if fail_on == "never":
        return 0
    if report.has_danger:
        return 2
    if fail_on == "warn" and report.has_warn:
        return 1
    return 0


def _render(report: Report, args) -> Optional[str]:
    """Return text for json/markdown, or None for the live CLI view."""
    if args.json:
        return render_json(report)
    if args.markdown:
        return render_md(report)
    return None


def main(argv: Optional[List[str]] = None) -> int:
    _setup_console()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.clear_cache:
        from .cache import DiskCache
        n = DiskCache().clear()
        sys.stderr.write(f"pkgguard: cleared cache ({n} entries)\n")
        return 0

    ecosystem = args.ecosystem
    if args.pypi:
        ecosystem = "pypi"
    if args.npm:
        ecosystem = "npm"

    items = _collect_items(args, parser, ecosystem)
    if not items:
        sys.stderr.write("pkgguard: no package/repo references found in input.\n")
        return 0

    report = vet_items(
        items,
        offline=args.offline, timeout=args.timeout, deep_fake_stars=args.deep,
        deep_source=args.scan, policy=args.policy,
        use_cache=not args.no_cache, cache_ttl=args.cache_ttl,
    )

    rendered = _render(report, args)
    if args.output:
        out_text = rendered if rendered is not None else _plain_capture(report)
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(out_text)
        except OSError as e:
            sys.stderr.write(f"pkgguard: could not write {args.output}: {e}\n")
            return 2
        sys.stderr.write(f"pkgguard: wrote {args.output}\n")
    elif rendered is not None:
        print(rendered)
    else:
        render_cli(report, use_color=not args.no_color)

    return _exit_code(report, args.fail_on)


def _plain_capture(report: Report) -> str:
    import io
    buf = io.StringIO()
    render_cli(report, use_color=False, stream=buf)
    return buf.getvalue()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
