"""Decide which parser to use and dispatch."""

from __future__ import annotations

import json
import re
from typing import List, Optional

from ..models import Ecosystem, Item
from .chat_text import parse_chat_text
from .manifests import parse_cargo, parse_gemfile, parse_gomod
from .normalize import GITHUB_SLUG_RE, strip_repo_suffix
from .package_json import parse_package_json
from .requirements import parse_requirements

_DEP_KEYS = ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies")
_GIT_URL = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+)", re.IGNORECASE)
_VERSION_OP = re.compile(r"(==|>=|<=|~=|!=|>|<)")
_BARE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
# Signals that the text is prose pasted from a chat, not a manifest.
_CHAT_HINT = re.compile(
    r"(pip[0-9]?\s+install|npm\s+(install|i)\b|yarn\s+add|pnpm\s+(add|install)"
    r"|`[^`]+`|^\s*[-*+]\s+|^\s*\d+[.)]\s+)",
    re.IGNORECASE | re.MULTILINE,
)

Format = str  # "auto" | "requirements" | "package-json" | "chat" | "list"


def _eco_default(ecosystem: Optional[str]) -> Ecosystem:
    if ecosystem is None:
        return Ecosystem.UNKNOWN
    try:
        return Ecosystem(ecosystem)
    except ValueError:
        return Ecosystem.UNKNOWN


def _parse_lines(text: str, source: str, default_eco: Ecosystem) -> List[Item]:
    """Parse a clean list / requirements block (one entry per line)."""
    items: List[Item] = []
    seen = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        gm = _GIT_URL.search(line)
        # A full github.com URL is always a repo; a bare owner/repo slug is only
        # treated as GitHub when the ecosystem is unspecified (so an explicit
        # -e packagist keeps "vendor/package" as a Packagist name).
        slug_is_github = bool(GITHUB_SLUG_RE.match(line)) and default_eco in (
            Ecosystem.UNKNOWN, Ecosystem.GITHUB
        )
        if gm or slug_is_github:
            if gm:
                owner, repo = gm.group(1), strip_repo_suffix(gm.group(2))
            else:
                owner, repo = line.split("/", 1)
                repo = strip_repo_suffix(repo)
            name = f"{owner}/{repo}"
            key = f"github:{name.lower()}"
            if key not in seen:
                seen.add(key)
                items.append(
                    Item(
                        raw=line, name=name, ecosystem=Ecosystem.GITHUB,
                        repo_url=f"https://github.com/{owner}/{repo}", source=source,
                    )
                )
            continue
        # name with optional version
        m = re.match(r"^([A-Za-z0-9@][A-Za-z0-9._/@-]*)", line)
        if not m:
            continue
        # Skip lines whose name was truncated by a non-ASCII/word char.
        end = m.end(1)
        if end < len(line) and (line[end].isalnum() or ord(line[end]) > 127):
            continue
        name = m.group(1)
        scoped = name.startswith("@")
        if not scoped:
            name = re.split(r"[\[=<>~!@ ]", name, maxsplit=1)[0]
        version = None
        vm = re.search(r"==\s*([A-Za-z0-9*.+!-]+)", line)
        if vm:
            version = vm.group(1)
        eco = Ecosystem.NPM if scoped else default_eco
        key = f"{eco}:{name.lower()}"
        if name and key not in seen:
            seen.add(key)
            items.append(Item(raw=line, name=name, ecosystem=eco, version=version, source=source))
    return items


def _looks_like_package_json(text: str) -> bool:
    t = text.lstrip()
    if not t.startswith("{"):
        return False
    try:
        data = json.loads(text)
    except Exception:
        return False
    return isinstance(data, dict) and any(k in data for k in _DEP_KEYS)


def parse_input(
    text: str,
    source: str = "input",
    fmt: Format = "auto",
    ecosystem: Optional[str] = None,
) -> List[Item]:
    """Parse ``text`` into a deduplicated list of :class:`Item`.

    ``fmt`` forces a parser; ``"auto"`` detects. ``ecosystem`` ("pypi"/"npm")
    sets the assumed ecosystem for otherwise-ambiguous bare names.
    """
    default_eco = _eco_default(ecosystem)

    if fmt == "package-json":
        return parse_package_json(text, source)
    if fmt == "requirements":
        return parse_requirements(text, source)
    if fmt == "cargo":
        return parse_cargo(text, source)
    if fmt == "gemfile":
        return parse_gemfile(text, source)
    if fmt == "go-mod":
        return parse_gomod(text, source)
    if fmt == "chat":
        return parse_chat_text(text, source, default_eco)
    if fmt == "list":
        return _parse_lines(text, source, default_eco)

    # auto-detect
    if _looks_like_package_json(text):
        return parse_package_json(text, source)
    if _CHAT_HINT.search(text):
        return parse_chat_text(text, source, default_eco)

    # Clean line-based input: requirements (has version ops) or a plain list.
    non_empty = [ln.split("#", 1)[0].strip() for ln in text.splitlines()]
    non_empty = [ln for ln in non_empty if ln]
    if non_empty and _VERSION_OP.search(text):
        # requirements-style -> assume PyPI unless caller said otherwise
        if default_eco is Ecosystem.UNKNOWN:
            default_eco = Ecosystem.PYPI
    return _parse_lines(text, source, default_eco)
