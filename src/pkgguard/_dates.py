"""Small date helpers shared by time-based checks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 timestamp (handles a trailing 'Z')."""
    if not ts or not isinstance(ts, str):
        return None
    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Fall back to date-only.
        try:
            dt = datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def age_days(ts: Optional[str]) -> Optional[float]:
    dt = parse_iso(ts)
    if dt is None:
        return None
    return (now_utc() - dt).total_seconds() / 86400.0
