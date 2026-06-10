"""SQLite database core: connections, init_db(), lightweight migrations.

Design:
- One connection per call via `get_conn()` context manager (sqlite handles
  short-lived connections well; WAL mode allows concurrent readers).
- Schema versioning through `schema_version` table; migrations are ordered
  SQL-script entries in MIGRATIONS. Add new entries, never edit old ones.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from typing import Iterator

from app.config.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)

_init_lock = threading.Lock()
_initialized_paths: set[str] = set()

MIGRATIONS: list[tuple[int, str]] = [
    (1, """
    CREATE TABLE IF NOT EXISTS users (
        id            TEXT PRIMARY KEY,
        username      TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role          TEXT NOT NULL DEFAULT 'user',
        display_name  TEXT NOT NULL DEFAULT '',
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL,
        last_login_at TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS conversations (
        id              TEXT PRIMARY KEY,
        user_id         TEXT NOT NULL REFERENCES users(id),
        title           TEXT NOT NULL DEFAULT '',
        mode            TEXT NOT NULL DEFAULT 'normal',
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL,
        last_message_at TEXT NOT NULL DEFAULT '',
        archived        INTEGER NOT NULL DEFAULT 0
    );
    CREATE INDEX IF NOT EXISTS idx_conversations_user
        ON conversations(user_id, archived, last_message_at);

    CREATE TABLE IF NOT EXISTS messages (
        id              TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES conversations(id),
        user_id         TEXT NOT NULL,
        role            TEXT NOT NULL,
        content         TEXT NOT NULL,
        content_type    TEXT NOT NULL DEFAULT 'text',
        intent          TEXT NOT NULL DEFAULT '',
        state           TEXT NOT NULL DEFAULT '',
        audio_asset_id  TEXT NOT NULL DEFAULT '',
        metadata_json   TEXT NOT NULL DEFAULT '{}',
        created_at      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON messages(conversation_id, created_at);
    CREATE INDEX IF NOT EXISTS idx_messages_user
        ON messages(user_id, created_at);

    CREATE TABLE IF NOT EXISTS memories (
        id                TEXT PRIMARY KEY,
        user_id           TEXT NOT NULL,
        memory_type       TEXT NOT NULL,
        content           TEXT NOT NULL,
        importance        INTEGER NOT NULL DEFAULT 3,
        confidence        REAL NOT NULL DEFAULT 0.8,
        source_message_id TEXT NOT NULL DEFAULT '',
        last_recalled_at  TEXT NOT NULL DEFAULT '',
        created_at        TEXT NOT NULL,
        updated_at        TEXT NOT NULL,
        deleted_at        TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_memories_user
        ON memories(user_id, memory_type, deleted_at);

    CREATE TABLE IF NOT EXISTS audio_assets (
        id            TEXT PRIMARY KEY,
        user_id       TEXT NOT NULL,
        message_id    TEXT NOT NULL DEFAULT '',
        asset_type    TEXT NOT NULL DEFAULT 'tts',
        file_path     TEXT NOT NULL DEFAULT '',
        public_url    TEXT NOT NULL DEFAULT '',
        duration_ms   INTEGER NOT NULL DEFAULT 0,
        provider      TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at    TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_audio_assets_user ON audio_assets(user_id);

    CREATE TABLE IF NOT EXISTS user_states (
        user_id            TEXT PRIMARY KEY,
        dialog_state       TEXT NOT NULL DEFAULT 'idle',
        emotional_state    TEXT NOT NULL DEFAULT 'neutral',
        sleep_mode_enabled INTEGER NOT NULL DEFAULT 0,
        call_mode_enabled  INTEGER NOT NULL DEFAULT 0,
        current_persona_id TEXT NOT NULL DEFAULT 'default',
        updated_at         TEXT NOT NULL
    );
    """),
]


def _db_path() -> str:
    return settings.database_url


@contextmanager
def get_conn(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a row-factory connection; commits on success."""
    path = db_path or _db_path()
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str | None = None) -> None:
    """Create / migrate schema. Idempotent and thread-safe."""
    path = db_path or _db_path()
    with _init_lock:
        if path in _initialized_paths:
            return
        with get_conn(path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version ("
                "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            applied = {r[0] for r in conn.execute("SELECT version FROM schema_version")}
            for version, script in MIGRATIONS:
                if version in applied:
                    continue
                log.info("Applying DB migration %d", version)
                conn.executescript(script)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) "
                    "VALUES (?, datetime('now'))", (version,))
        _initialized_paths.add(path)


def reset_init_cache() -> None:
    """Testing helper: forget which paths were initialized."""
    with _init_lock:
        _initialized_paths.clear()
