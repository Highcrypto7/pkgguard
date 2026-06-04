"""JSON report renderer."""

from __future__ import annotations

import json

from ..models import Report


def render_json(report: Report, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), indent=indent, ensure_ascii=False)
