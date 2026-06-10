"""Conversation persistence."""
from __future__ import annotations

from app.models.schemas import Conversation
from app.repositories.db import get_conn
from app.utils.ids import new_id
from app.utils.time import now_iso


def _row_to_conv(row) -> Conversation:
    return Conversation(
        id=row["id"], user_id=row["user_id"], title=row["title"], mode=row["mode"],
        created_at=row["created_at"], updated_at=row["updated_at"],
        last_message_at=row["last_message_at"], archived=bool(row["archived"]),
    )


def create(user_id: str, title: str = "", mode: str = "normal") -> Conversation:
    now = now_iso()
    conv = Conversation(
        id=new_id("conv"), user_id=user_id, title=title or "新的对话",
        mode=mode, created_at=now, updated_at=now, last_message_at=now)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO conversations (id, user_id, title, mode, created_at,"
            " updated_at, last_message_at, archived) VALUES (?,?,?,?,?,?,?,0)",
            (conv.id, conv.user_id, conv.title, conv.mode,
             conv.created_at, conv.updated_at, conv.last_message_at))
    return conv


def get(conversation_id: str) -> Conversation | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return _row_to_conv(row) if row else None


def list_for_user(user_id: str, include_archived: bool = False,
                  limit: int = 50) -> list[Conversation]:
    sql = "SELECT * FROM conversations WHERE user_id = ?"
    if not include_archived:
        sql += " AND archived = 0"
    sql += " ORDER BY last_message_at DESC LIMIT ?"
    with get_conn() as conn:
        rows = conn.execute(sql, (user_id, limit)).fetchall()
    return [_row_to_conv(r) for r in rows]


def latest_active(user_id: str) -> Conversation | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE user_id = ? AND archived = 0"
            " ORDER BY last_message_at DESC LIMIT 1", (user_id,)).fetchone()
    return _row_to_conv(row) if row else None


def touch(conversation_id: str) -> None:
    now = now_iso()
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET last_message_at = ?, updated_at = ? WHERE id = ?",
            (now, now, conversation_id))


def set_title(conversation_id: str, title: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (title[:80], now_iso(), conversation_id))


def set_archived(conversation_id: str, archived: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE conversations SET archived = ?, updated_at = ? WHERE id = ?",
            (int(archived), now_iso(), conversation_id))


def delete(conversation_id: str) -> None:
    """Hard delete a conversation and its messages."""
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
        conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
