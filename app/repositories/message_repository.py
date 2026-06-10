"""Message persistence."""
from __future__ import annotations

from typing import Any

from app.models.schemas import Message, _meta_dumps, _meta_loads
from app.repositories.db import get_conn
from app.utils.ids import new_id
from app.utils.time import now_iso


def _row_to_message(row) -> Message:
    return Message(
        id=row["id"], conversation_id=row["conversation_id"], user_id=row["user_id"],
        role=row["role"], content=row["content"], content_type=row["content_type"],
        intent=row["intent"], state=row["state"], audio_asset_id=row["audio_asset_id"],
        metadata=_meta_loads(row["metadata_json"]), created_at=row["created_at"],
    )


def create(conversation_id: str, user_id: str, role: str, content: str,
           content_type: str = "text", intent: str = "", state: str = "",
           audio_asset_id: str = "", metadata: dict[str, Any] | None = None) -> Message:
    msg = Message(
        id=new_id("msg"), conversation_id=conversation_id, user_id=user_id,
        role=role, content=content, content_type=content_type, intent=intent,
        state=state, audio_asset_id=audio_asset_id, metadata=metadata or {},
        created_at=now_iso())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, user_id, role, content,"
            " content_type, intent, state, audio_asset_id, metadata_json, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (msg.id, msg.conversation_id, msg.user_id, msg.role, msg.content,
             msg.content_type, msg.intent, msg.state, msg.audio_asset_id,
             _meta_dumps(msg.metadata), msg.created_at))
    return msg


def get(message_id: str) -> Message | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
    return _row_to_message(row) if row else None


def list_for_conversation(conversation_id: str, limit: int = 100,
                          before: str = "") -> list[Message]:
    """Messages in chronological order; `before` is an ISO timestamp cursor."""
    sql = "SELECT * FROM messages WHERE conversation_id = ?"
    params: list[Any] = [conversation_id]
    if before:
        sql += " AND created_at < ?"
        params.append(before)
    sql += " ORDER BY created_at DESC, rowid DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_message(r) for r in reversed(rows)]


def recent_turns(conversation_id: str, max_turns: int = 10) -> list[dict[str, str]]:
    """Last N user/assistant messages as LLM history [{'role','content'}, ...]."""
    msgs = list_for_conversation(conversation_id, limit=max_turns * 2)
    return [{"role": m.role, "content": m.content}
            for m in msgs if m.role in ("user", "assistant") and m.content]


def update_metadata(message_id: str, metadata: dict[str, Any]) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE messages SET metadata_json = ? WHERE id = ?",
                     (_meta_dumps(metadata), message_id))


def set_audio_asset(message_id: str, audio_asset_id: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE messages SET audio_asset_id = ? WHERE id = ?",
                     (audio_asset_id, message_id))


def delete(message_id: str, user_id: str) -> bool:
    """Delete a message owned by user_id. Returns True if a row was removed."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM messages WHERE id = ? AND user_id = ?",
                           (message_id, user_id))
        return cur.rowcount > 0


def list_for_user(user_id: str, limit: int = 1000) -> list[Message]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE user_id = ?"
                " ORDER BY created_at DESC, rowid DESC LIMIT ?", (user_id, limit)).fetchall()
    return [_row_to_message(r) for r in reversed(rows)]
