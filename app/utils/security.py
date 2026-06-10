"""Security helpers: path safety, login throttling."""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict

from app.utils.logger import get_logger

log = get_logger(__name__)


def safe_join(base_dir: str, filename: str) -> str | None:
    """Join filename to base_dir, refusing path traversal. Returns None if unsafe."""
    base = os.path.abspath(base_dir)
    candidate = os.path.normpath(os.path.join(base, filename))
    if candidate == base or not candidate.startswith(base + os.sep):
        log.warning("Blocked path traversal attempt: %r", filename)
        return None
    return candidate


class LoginThrottle:
    """In-memory failed-login limiter: max_attempts per window per key."""

    def __init__(self, max_attempts: int = 5, window_sec: int = 300) -> None:
        self.max_attempts = max_attempts
        self.window_sec = window_sec
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def is_blocked(self, key: str) -> bool:
        cutoff = time.time() - self.window_sec
        with self._lock:
            attempts = [t for t in self._attempts.get(key, []) if t > cutoff]
            self._attempts[key] = attempts
            return len(attempts) >= self.max_attempts

    def record_failure(self, key: str) -> None:
        with self._lock:
            self._attempts[key].append(time.time())

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)
