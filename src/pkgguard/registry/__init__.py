"""Registry existence + metadata lookups (PyPI, npm, crates.io, Go, RubyGems)."""

from __future__ import annotations

from .crates import fetch_crates
from .golang import fetch_go
from .more import fetch_nuget, fetch_packagist, fetch_pub
from .npm import fetch_npm
from .pypi import fetch_pypi
from .rubygems import fetch_rubygems

__all__ = [
    "fetch_pypi", "fetch_npm", "fetch_crates", "fetch_go", "fetch_rubygems",
    "fetch_packagist", "fetch_nuget", "fetch_pub",
]
