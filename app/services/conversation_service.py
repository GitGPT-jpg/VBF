"""ConversationService — session lifecycle around conversations."""
from __future__ import annotations

from app.models.schemas import Conversation
from app.repositories import conversation_repository as conv_repo
from app.utils.logger import get_logger

log = get_logger(__name__)


def get_or_create(user_id: str, conversation_id: str = "") -> Conversation:
    """Resolve a conversation for a request; auto-create when missing.

    Ownership is enforced: a conversation_id belonging to another user is
    treated as missing.
    """
    if conversation_id:
        conv = conv_repo.get(conversation_id)
        if conv and conv.user_id == user_id and not conv.archived:
            return conv
    conv = conv_repo.latest_active(user_id)
    if conv:
        return conv
    return conv_repo.create(user_id)


def create(user_id: str, title: str = "") -> Conversation:
    return conv_repo.create(user_id, title=title)


def list_for_user(user_id: str, include_archived: bool = False) -> list[Conversation]:
    return conv_repo.list_for_user(user_id, include_archived=include_archived)


def archive(conversation_id: str, user_id: str) -> bool:
    conv = conv_repo.get(conversation_id)
    if not conv or conv.user_id != user_id:
        return False
    conv_repo.set_archived(conversation_id, True)
    return True


def delete(conversation_id: str, user_id: str) -> bool:
    conv = conv_repo.get(conversation_id)
    if not conv or conv.user_id != user_id:
        return False
    conv_repo.delete(conversation_id)
    return True


def maybe_autotitle(conv: Conversation, first_user_message: str) -> None:
    """Title new conversations from the first user message."""
    if conv.title in ("", "新的对话") and first_user_message:
        conv_repo.set_title(conv.id, first_user_message[:30])
