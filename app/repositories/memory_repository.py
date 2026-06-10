"""Long-term memory persistence."""
from __future__ import annotations

from app.models.schemas import Memory
from app.repositories.db import get_conn
from app.utils.ids import new_id
from app.utils.time import now_iso


def _row_to_memory(row) -> Memory:
    return Memory(
        id=row["id"], user_id=row["user_id"], memory_type=row["memory_type"],
        content=row["content"], importance=row["importance"],
        confidence=row["confidence"], source_message_id=row["source_message_id"],
        last_recalled_at=row["last_recalled_at"], created_at=row["created_at"],
        updated_at=row["updated_at"], deleted_at=row["deleted_at"],
    )


def create(user_id: str, memory_type: str, content: str, importance: int = 3,
           confidence: float = 0.8, source_message_id: str = "") -> Memory:
    now = now_iso()
    mem = Memory(
        id=new_id("mem"), user_id=user_id, memory_type=memory_type, content=content,
        importance=max(1, min(5, importance)),
        confidence=max(0.0, min(1.0, confidence)),
        source_message_id=source_message_id, created_at=now, updated_at=now)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO memories (id, user_id, memory_type, content, importance,"
            " confidence, source_message_id, last_recalled_at, created_at,"
            " updated_at, deleted_at) VALUES (?,?,?,?,?,?,?,'',?,?,'')",
            (mem.id, mem.user_id, mem.memory_type, mem.content, mem.importance,
             mem.confidence, mem.source_message_id, mem.created_at, mem.updated_at))
    return mem


def get(memory_id: str) -> Memory | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
    return _row_to_memory(row) if row else None


def list_for_user(user_id: str, memory_type: str = "", limit: int = 200,
                  include_deleted: bool = False) -> list[Memory]:
    sql = "SELECT * FROM memories WHERE user_id = ?"
    params: list = [user_id]
    if not include_deleted:
        sql += " AND deleted_at = ''"
    if memory_type:
        sql += " AND memory_type = ?"
        params.append(memory_type)
    sql += " ORDER BY importance DESC, updated_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_memory(r) for r in rows]


def list_recent(user_id: str, since_iso: str, limit: int = 50) -> list[Memory]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM memories WHERE user_id = ? AND deleted_at = ''"
            " AND created_at >= ? ORDER BY created_at DESC LIMIT ?",
            (user_id, since_iso, limit)).fetchall()
    return [_row_to_memory(r) for r in rows]


def find_duplicate(user_id: str, memory_type: str, content: str) -> Memory | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM memories WHERE user_id = ? AND memory_type = ?"
            " AND content = ? AND deleted_at = ''",
            (user_id, memory_type, content)).fetchone()
    return _row_to_memory(row) if row else None


def update(memory_id: str, user_id: str, content: str | None = None,
           importance: int | None = None, confidence: float | None = None) -> bool:
    sets, params = ["updated_at = ?"], [now_iso()]
    if content is not None:
        sets.append("content = ?")
        params.append(content)
    if importance is not None:
        sets.append("importance = ?")
        params.append(max(1, min(5, importance)))
    if confidence is not None:
        sets.append("confidence = ?")
        params.append(max(0.0, min(1.0, confidence)))
    params.extend([memory_id, user_id])
    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE memories SET {', '.join(sets)} WHERE id = ? AND user_id = ?",
            params)
        return cur.rowcount > 0


def touch_recalled(memory_ids: list[str]) -> None:
    if not memory_ids:
        return
    now = now_iso()
    with get_conn() as conn:
        conn.executemany(
            "UPDATE memories SET last_recalled_at = ? WHERE id = ?",
            [(now, mid) for mid in memory_ids])


def soft_delete(memory_id: str, user_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE memories SET deleted_at = ? WHERE id = ? AND user_id = ?"
            " AND deleted_at = ''", (now_iso(), memory_id, user_id))
        return cur.rowcount > 0


def clear_for_user(user_id: str) -> int:
    """Soft-delete all memories of a user; returns count."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE memories SET deleted_at = ? WHERE user_id = ? AND deleted_at = ''",
            (now_iso(), user_id))
        return cur.rowcount
