"""Parse ``package.json`` (or a raw dependency object) into npm items."""

from __future__ import annotations

import json
from typing import List

from ..models import Ecosystem, Item

_DEP_KEYS = (
    "dependencies",
    "devDependencies",
    "peerDependencies",
    "optionalDependencies",
)


def parse_package_json(text: str, source: str = "package.json") -> List[Item]:
    try:
        data = json.loads(text)
    except Exception:
        return []
    if not isinstance(data, dict):
        return []

    items: List[Item] = []
    seen = set()
    for key in _DEP_KEYS:
        deps = data.get(key)
        if not isinstance(deps, dict):
            continue
        for name, spec in deps.items():
            if name in seen:
                continue
            seen.add(name)
            version = None
            if isinstance(spec, str):
                # Pin like "1.2.3" -> exact; "^1.2" / ">=1" -> leave as range note
                s = spec.strip()
                if s and s[0].isdigit():
                    version = s
            items.append(
                Item(
                    raw=f"{name}: {spec}",
                    name=name,
                    ecosystem=Ecosystem.NPM,
                    version=version,
                    source=f"{source}:{key}",
                )
            )
    return items
