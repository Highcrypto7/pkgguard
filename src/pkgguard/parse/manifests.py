"""Parsers for Cargo.toml, Gemfile, and go.mod (lightweight, no TOML dep)."""

from __future__ import annotations

import re
from typing import List

from ..models import Ecosystem, Item

_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_KEYVAL = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=")
_GEM = re.compile(r"""^\s*gem\s+['"]([^'"]+)['"]""")
_GOMOD_LINE = re.compile(r"^\s*([^\s]+)\s+v\S+")


def parse_cargo(text: str, source: str = "Cargo.toml") -> List[Item]:
    items: List[Item] = []
    seen = set()
    in_deps = False
    for raw in text.splitlines():
        m = _SECTION.match(raw)
        if m:
            sect = m.group(1).strip()
            # [dependencies], [dev-dependencies], [build-dependencies],
            # and table form [dependencies.foo]
            parts = sect.split(".")
            if parts[0].endswith("dependencies"):
                if len(parts) > 1:
                    # [dependencies.foo] -> foo is the crate; its key=val lines
                    # are properties (version, features), NOT crate names.
                    in_deps = False
                    name = parts[1]
                    if name not in seen:
                        seen.add(name)
                        items.append(Item(raw=raw.strip(), name=name,
                                           ecosystem=Ecosystem.CRATES, source=source))
                else:
                    in_deps = True  # plain [dependencies] table
            else:
                in_deps = False
            continue
        if in_deps:
            km = _KEYVAL.match(raw)
            if km and km.group(1) not in seen:
                name = km.group(1)
                seen.add(name)
                items.append(Item(raw=raw.strip(), name=name,
                                  ecosystem=Ecosystem.CRATES, source=source))
    return items


def parse_gemfile(text: str, source: str = "Gemfile") -> List[Item]:
    items, seen = [], set()
    for raw in text.splitlines():
        m = _GEM.match(raw)
        if m and m.group(1) not in seen:
            seen.add(m.group(1))
            items.append(Item(raw=raw.strip(), name=m.group(1),
                              ecosystem=Ecosystem.RUBYGEMS, source=source))
    return items


def parse_gomod(text: str, source: str = "go.mod") -> List[Item]:
    items, seen = [], set()
    in_block = False
    for raw in text.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("module ") or line.startswith("go ") or line.startswith("toolchain "):
            continue
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block and line == ")":
            in_block = False
            continue
        target = line
        if line.startswith("require "):
            target = line[len("require "):].strip()
        if in_block or line.startswith("require ") or (target and target[0].isalpha()):
            m = _GOMOD_LINE.match(target)
            if m:
                name = m.group(1)
                if name not in seen and "/" in name:
                    seen.add(name)
                    items.append(Item(raw=line, name=name,
                                      ecosystem=Ecosystem.GO, source=source))
    return items
