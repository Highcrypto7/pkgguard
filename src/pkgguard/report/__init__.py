"""Report aggregation and rendering."""

from __future__ import annotations

from .aggregate import finalize
from .render_cli import render_cli
from .render_json import render_json
from .render_md import render_md

__all__ = ["finalize", "render_cli", "render_json", "render_md"]
