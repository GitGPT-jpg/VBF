"""Typed schemas shared across layers (dataclasses, no ORM)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Role = Literal["user", "assistant", "system"]
ContentType = Literal["text", "voice", "song", "card"]
MemoryType = Literal["profile", "preference", "episodic", "emotional", "relationship", "task"]
AssetType = Literal["tts", "song", "uploaded_voice"]


def _meta_dumps(meta: dict[str, Any] | None) -> str:
    return json.dumps(meta or {}, ensure_ascii=False)


def _meta_loads(raw: str | None) -> dict[str, Any]:
    try:
        return json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        return {}


@dataclass
class User:
    id: str
    username: str
    password_hash: str
    role: str = "user"
    display_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    last_login_at: str = ""


@dataclass
class Conversation:
    id: str
    user_id: str
    title: str = ""
    mode: str = "normal"
    created_at: str = ""
    updated_at: str = ""
    last_message_at: str = ""
    archived: bool = False


@dataclass
class Message:
    id: str
    conversation_id: str
    user_id: str
    role: Role
    content: str
    content_type: ContentType = "text"
    intent: str = ""
    state: str = ""
    audio_asset_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Memory:
    id: str
    user_id: str
    memory_type: MemoryType
    content: str
    importance: int = 3          # 1-5
    confidence: float = 0.8      # 0-1
    source_message_id: str = ""
    last_recalled_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    deleted_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AudioAsset:
    id: str
    user_id: str
    message_id: str = ""
    asset_type: AssetType = "tts"
    file_path: str = ""
    public_url: str = ""
    duration_ms: int = 0
    provider: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


@dataclass
class UserState:
    user_id: str
    dialog_state: str = "idle"
    emotional_state: str = "neutral"
    sleep_mode_enabled: bool = False
    call_mode_enabled: bool = False
    current_persona_id: str = "default"
    updated_at: str = ""


@dataclass
class IntentResult:
    intent: str
    confidence: float = 1.0
    reason: str = ""
    slots: dict[str, Any] = field(default_factory=dict)
    source: str = "rule"  # rule | llm | fallback | cache


@dataclass
class ExtractedMemory:
    type: str
    content: str
    importance: int = 3
    confidence: float = 0.5


__all__ = [
    "Role", "ContentType", "MemoryType", "AssetType",
    "User", "Conversation", "Message", "Memory", "AudioAsset", "UserState",
    "IntentResult", "ExtractedMemory",
    "_meta_dumps", "_meta_loads",
]
