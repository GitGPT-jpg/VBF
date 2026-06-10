"""ID generation helpers."""
from __future__ import annotations

import uuid


def new_id(prefix: str = "") -> str:
    """Generate a URL-safe unique id, optionally prefixed (e.g. 'msg_...')."""
    raw = uuid.uuid4().hex
    return f"{prefix}_{raw}" if prefix else raw
