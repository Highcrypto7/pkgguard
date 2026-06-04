"""Name normalization helpers shared by parsers and checks."""

from __future__ import annotations

import re
from typing import Optional, Tuple

_GH_IN_URL = re.compile(r"github\.com[/:]([A-Za-z0-9][\w.-]*)/([A-Za-z0-9][\w.-]*)", re.I)

# PEP 503: a normalized PyPI name lowercases and collapses runs of -_. to -.
_PEP503_RUN = re.compile(r"[-_.]+")

# Valid-ish package tokens (used to reject prose words / punctuation).
PYPI_NAME_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?$")
NPM_NAME_RE = re.compile(r"^(?:@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*$")
GITHUB_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


def normalize_pypi(name: str) -> str:
    """PEP 503 normalized form, for comparison/lookup."""
    return _PEP503_RUN.sub("-", name).lower()


def normalize_npm(name: str) -> str:
    return name.strip().lower()


def strip_repo_suffix(repo: str) -> str:
    return repo[:-4] if repo.endswith(".git") else repo


def looks_like_pypi_name(token: str) -> bool:
    return bool(PYPI_NAME_RE.match(token)) and len(token) <= 100


def looks_like_npm_name(token: str) -> bool:
    return bool(NPM_NAME_RE.match(token)) and len(token) <= 214


def github_owner_repo(url: Optional[str]) -> Optional[Tuple[str, str]]:
    """Extract ``(owner, repo)`` from any string containing a GitHub URL."""
    if not url:
        return None
    m = _GH_IN_URL.search(url)
    if not m:
        return None
    return m.group(1), strip_repo_suffix(m.group(2).rstrip("/").split("#")[0].split("?")[0])
