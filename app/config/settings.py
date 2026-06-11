"""Environment-driven application settings.

All sensitive configuration is read from `.env` / process environment.
`settings.validate()` performs startup safety checks (see safety_service).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(_PROJECT_DIR, ".env"))


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Typed, immutable application settings."""

    # ── App ──
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    web_secret_key: str = field(default_factory=lambda: os.getenv("WEB_SECRET_KEY", ""))
    web_port: int = field(default_factory=lambda: _env_int("WEB_PORT", 5000))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    project_dir: str = _PROJECT_DIR

    # ── Database ──
    database_url: str = field(default_factory=lambda: (
        os.getenv("DATABASE_URL") or os.path.join(_PROJECT_DIR, "data", "app.db")))
    legacy_log_db: str = field(default_factory=lambda: os.path.join(
        _PROJECT_DIR, "logs", "conversations.db"))

    # ── LLM ──
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_base_url: str = field(default_factory=lambda: os.getenv(
        "ANTHROPIC_BASE_URL", "https://api.anthropic.com") or "https://api.anthropic.com")
    anthropic_model: str = field(default_factory=lambda: os.getenv(
        "ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))

    # ── TTS / Voice ──
    tts_provider: str = field(default_factory=lambda: os.getenv("TTS_PROVIDER", "edge"))
    elevenlabs_api_key: str = field(default_factory=lambda: os.getenv("ELEVENLABS_API_KEY", ""))
    elevenlabs_voice_id: str = field(default_factory=lambda: os.getenv("ELEVENLABS_VOICE_ID", ""))
    fish_audio_api_key: str = field(default_factory=lambda: os.getenv("FISH_AUDIO_API_KEY", ""))
    replicate_api_key: str = field(default_factory=lambda: os.getenv("REPLICATE_API_KEY", ""))

    # ── Feature flags ──
    enable_singing: bool = field(default_factory=lambda: _env_bool("ENABLE_SINGING", True))
    enable_memory_extraction: bool = field(
        default_factory=lambda: _env_bool("ENABLE_MEMORY_EXTRACTION", True))
    enable_streaming: bool = field(default_factory=lambda: _env_bool("ENABLE_STREAMING", True))

    # ── Legacy bootstrap users (migrated into DB on first run) ──
    bootstrap_owner_user: str = field(default_factory=lambda: os.getenv("WEB_USER", "admin"))
    bootstrap_owner_pass: str = field(default_factory=lambda: os.getenv("WEB_PASS", "admin"))
    bootstrap_companion_user: str = field(default_factory=lambda: os.getenv("WEB_GF_USER", "girl"))
    bootstrap_companion_pass: str = field(default_factory=lambda: os.getenv("WEB_GF_PASS", "girl"))

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def validate(self) -> list[str]:
        """Return a list of fatal configuration problems (empty == OK)."""
        problems: list[str] = []
        if self.is_production:
            if not self.web_secret_key or self.web_secret_key in (
                    "insecure-dev-key", "change-me"):
                problems.append("WEB_SECRET_KEY must be set to a strong value in production.")
            if self.bootstrap_owner_user == "admin" and self.bootstrap_owner_pass == "admin":
                problems.append("Default admin/admin credentials are forbidden in production.")
        return problems

    def warnings(self) -> list[str]:
        """Non-fatal configuration warnings."""
        warns: list[str] = []
        if not self.web_secret_key:
            warns.append("WEB_SECRET_KEY not set — using an ephemeral dev key "
                         "(sessions reset on restart).")
        if not self.anthropic_api_key:
            warns.append("ANTHROPIC_API_KEY not set — LLM replies will fall back.")
        return warns


settings = Settings()
