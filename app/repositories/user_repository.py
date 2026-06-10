"""User persistence (users + user_states tables)."""
from __future__ import annotations

from app.models.schemas import User, UserState
from app.repositories.db import get_conn
from app.utils.ids import new_id
from app.utils.time import now_iso


def _row_to_user(row) -> User:
    return User(
        id=row["id"], username=row["username"], password_hash=row["password_hash"],
        role=row["role"], display_name=row["display_name"],
        created_at=row["created_at"], updated_at=row["updated_at"],
        last_login_at=row["last_login_at"],
    )


def create_user(username: str, password_hash: str, role: str = "user",
                display_name: str = "") -> User:
    now = now_iso()
    user = User(
        id=new_id("usr"), username=username, password_hash=password_hash,
        role=role, display_name=display_name or username,
        created_at=now, updated_at=now,
    )
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (id, username, password_hash, role, display_name,"
            " created_at, updated_at, last_login_at) VALUES (?,?,?,?,?,?,?,'')",
            (user.id, user.username, user.password_hash, user.role,
             user.display_name, user.created_at, user.updated_at))
    return user


def get_by_username(username: str) -> User | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    return _row_to_user(row) if row else None


def get_by_id(user_id: str) -> User | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def update_password(user_id: str, password_hash: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (password_hash, now_iso(), user_id))


def touch_last_login(user_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?", (now_iso(), user_id))


def list_users() -> list[User]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [_row_to_user(r) for r in rows]


# ── user_states ──────────────────────────────────────────────────────────────

def get_state(user_id: str) -> UserState:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM user_states WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return UserState(user_id=user_id, updated_at=now_iso())
    return UserState(
        user_id=row["user_id"], dialog_state=row["dialog_state"],
        emotional_state=row["emotional_state"],
        sleep_mode_enabled=bool(row["sleep_mode_enabled"]),
        call_mode_enabled=bool(row["call_mode_enabled"]),
        current_persona_id=row["current_persona_id"], updated_at=row["updated_at"],
    )


def save_state(state: UserState) -> None:
    state.updated_at = now_iso()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_states (user_id, dialog_state, emotional_state,"
            " sleep_mode_enabled, call_mode_enabled, current_persona_id, updated_at)"
            " VALUES (?,?,?,?,?,?,?)"
            " ON CONFLICT(user_id) DO UPDATE SET"
            " dialog_state=excluded.dialog_state,"
            " emotional_state=excluded.emotional_state,"
            " sleep_mode_enabled=excluded.sleep_mode_enabled,"
            " call_mode_enabled=excluded.call_mode_enabled,"
            " current_persona_id=excluded.current_persona_id,"
            " updated_at=excluded.updated_at",
            (state.user_id, state.dialog_state, state.emotional_state,
             int(state.sleep_mode_enabled), int(state.call_mode_enabled),
             state.current_persona_id, state.updated_at))
