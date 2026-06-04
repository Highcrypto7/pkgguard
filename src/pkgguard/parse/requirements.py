"""Parse pip ``requirements.txt`` style input into PyPI items."""

from __future__ import annotations

import re
from typing import List

from ..models import Ecosystem, Item
from .normalize import strip_repo_suffix

# name[extras](==|>=|<=|~=|!=|>|<|===)version ; markers
_REQ_LINE = re.compile(
    r"""^\s*
        (?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)      # distribution name
        (?:\[[^\]]*\])?                           # optional extras
        \s*
        (?:
            (?P<op>==|===|>=|<=|~=|!=|>|<)         # version operator
            \s*(?P<ver>[A-Za-z0-9*.+!-]+)
        )?
    """,
    re.VERBOSE,
)

_GIT_URL = re.compile(r"github\.com[/:]([\w.-]+)/([\w.-]+)", re.IGNORECASE)


def parse_requirements(text: str, source: str = "requirements.txt") -> List[Item]:
    items: List[Item] = []
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()  # drop comments
        if not line:
            continue

        # Editable / VCS installs: -e git+https://github.com/owner/repo.git
        if line.startswith("-"):
            m = _GIT_URL.search(line)
            if m:
                owner, repo = m.group(1), strip_repo_suffix(m.group(2))
                items.append(
                    Item(
                        raw=raw_line.strip(),
                        name=f"{owner}/{repo}",
                        ecosystem=Ecosystem.GITHUB,
                        repo_url=f"https://github.com/{owner}/{repo}",
                        source=source,
                    )
                )
            continue  # other options (-r, --index-url, ...) are not packages

        # A bare VCS URL on its own line.
        if line.startswith(("git+", "http://", "https://")):
            m = _GIT_URL.search(line)
            if m:
                owner, repo = m.group(1), strip_repo_suffix(m.group(2))
                items.append(
                    Item(
                        raw=line,
                        name=f"{owner}/{repo}",
                        ecosystem=Ecosystem.GITHUB,
                        repo_url=f"https://github.com/{owner}/{repo}",
                        source=source,
                    )
                )
            continue

        m = _REQ_LINE.match(line)
        if not m:
            continue
        # Reject lines whose name was truncated by a non-ASCII/word char that the
        # ASCII name pattern couldn't consume (e.g. "Děčín==1") rather than
        # silently vetting the wrong truncated name.
        end = m.end("name")
        if end < len(line) and (line[end].isalnum() or ord(line[end]) > 127):
            continue
        version = m.group("ver") if m.group("op") in ("==", "===") else None
        items.append(
            Item(
                raw=line,
                name=m.group("name"),
                ecosystem=Ecosystem.PYPI,
                version=version,
                source=source,
            )
        )
    return items
