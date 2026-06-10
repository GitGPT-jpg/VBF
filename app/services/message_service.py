"""MessageService — persistence + serialization of chat messages."""
from __future__ import annotations

from typing import Any

from app.models.schemas import Message
from app.repositories import (
    audio_repository as audio_repo,
    conversation_repository as conv_repo,
    message_repository as msg_repo,
)


def save_user_message(conversation_id: str, user_id: str, content: str,
                      intent: str = "", state: str = "") -> Message:
    msg = msg_repo.create(conversation_id, user_id, "user", content,
                          intent=intent, state=state)
    conv_repo.touch(conversation_id)
    return msg


def save_assistant_message(conversation_id: str, user_id: str, content: str,
                           content_type: str = "text", intent: str = "",
                           state: str = "", audio_asset_id: str = "",
                           metadata: dict[str, Any] | None = None) -> Message:
    msg = msg_repo.create(conversation_id, user_id, "assistant", content,
                          content_type=content_type, intent=intent, state=state,
                          audio_asset_id=audio_asset_id, metadata=metadata)
    conv_repo.touch(conversation_id)
    return msg


def history(conversation_id: str, limit: int = 100, before: str = "") -> list[Message]:
    return msg_repo.list_for_conversation(conversation_id, limit=limit, before=before)


def llm_history(conversation_id: str, max_turns: int = 10) -> list[dict[str, str]]:
    return msg_repo.recent_turns(conversation_id, max_turns=max_turns)


def serialize(msg: Message) -> dict[str, Any]:
    """Message → frontend dict, resolving audio asset URL."""
    audio_url = ""
    if msg.audio_asset_id:
        asset = audio_repo.get(msg.audio_asset_id)
        if asset:
            audio_url = asset.public_url
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "role": msg.role,
        "content": msg.content,
        "content_type": msg.content_type,
        "intent": msg.intent,
        "audio_url": audio_url,
        "metadata": msg.metadata,
        "created_at": msg.created_at,
    }


def toggle_favorite(message_id: str, user_id: str) -> bool:
    msg = msg_repo.get(message_id)
    if not msg or msg.user_id != user_id:
        return False
    meta = dict(msg.metadata)
    meta["favorite"] = not meta.get("favorite", False)
    msg_repo.update_metadata(message_id, meta)
    return True


def delete(message_id: str, user_id: str) -> bool:
    return msg_repo.delete(message_id, user_id)
