"""Time helpers — ISO-8601 timestamps used across the app."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def now_iso() -> str:
    """Current local time as ISO-8601 string (second precision)."""
    return datetime.now().isoformat(timespec="seconds")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def days_ago_iso(days: int) -> str:
    return (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")
