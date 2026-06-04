"""Input parsing: raw text -> list[Item].

Four supported shapes, auto-detected (or forced via the CLI):

* ``requirements.txt`` style  -> PyPI items
* ``package.json`` (JSON)     -> npm items
* a plain list (one name/line)
* free chat text pasted from ChatGPT/Claude (the headline use case):
  install commands, GitHub links, code spans and bullet lists are mined for
  package/repo references.

See :func:`parse_input` for the entry point.
"""

from __future__ import annotations

from .detect import parse_input

__all__ = ["parse_input"]
