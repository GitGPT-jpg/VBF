"""Central logging with secret redaction."""
from __future__ import annotations

import logging
import re
import sys

_REDACT_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9_\-]{8})[A-Za-z0-9_\-]+"),
    re.compile(r"(api[_-]?key['\"=:\s]+)[A-Za-z0-9_\-]{12,}", re.IGNORECASE),
    re.compile(r"(Bearer\s+)[A-Za-z0-9_\-.]{12,}"),
]


class _RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for pat in _REDACT_PATTERNS:
            msg = pat.sub(r"\1***", msg)
        return msg


_configured = False


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger once with UTF-8-safe stream handler."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_RedactingFormatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s", datefmt="%H:%M:%S"))
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
