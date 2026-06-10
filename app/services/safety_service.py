"""SafetyService — startup checks and data-access guards."""
from __future__ import annotations

import sys

from app.config.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


def run_startup_checks(strict: bool | None = None) -> None:
    """Validate configuration. Fatal problems exit in production."""
    problems = settings.validate()
    for warning in settings.warnings():
        log.warning("CONFIG: %s", warning)
    if problems:
        for problem in problems:
            log.error("CONFIG FATAL: %s", problem)
        if strict if strict is not None else settings.is_production:
            sys.exit("Refusing to start with insecure production configuration.")


def assert_owner(role: str) -> bool:
    return role == "owner"
