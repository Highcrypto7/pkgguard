"""GitHub repository metadata (REST API v3, optional token)."""

from __future__ import annotations

from .api import fetch_license_text, fetch_readme, fetch_repo, fetch_stargazers_sample

__all__ = [
    "fetch_repo", "fetch_stargazers_sample", "fetch_license_text", "fetch_readme",
]
