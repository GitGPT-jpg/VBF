"""One-off migration: import legacy logs/conversations.db into the new schema.

Usage:
    python migrations/import_legacy_logs.py

Each legacy row (ts, username, intent, user_msg, bot_reply, audio_path) becomes
a user + a "导入的历史对话" conversation + two messages. Idempotent: skips if a
legacy-import conversation already exists for the user.
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config.settings import settings  # noqa: E402
from app.repositories import (  # noqa: E402
    conversation_repository as conv_repo,
    message_repository as msg_repo,
    user_repository as user_repo,
)
from app.repositories.db import init_db  # noqa: E402

LEGACY_TITLE = "导入的历史对话"


def import_legacy(legacy_db: str | None = None) -> int:
    """Import legacy rows; returns number of imported message pairs."""
    path = legacy_db or settings.legacy_log_db
    if not os.path.exists(path):
        print(f"No legacy DB found at {path}; nothing to import.")
        return 0

    init_db()
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM conversations ORDER BY id").fetchall()
    con.close()

    imported = 0
    conv_cache: dict[str, str] = {}
    for row in rows:
        username = row["username"]
        user = user_repo.get_by_username(username)
        if user is None:
            from werkzeug.security import generate_password_hash
            user = user_repo.create_user(
                username, generate_password_hash(os.urandom(16).hex()))

        if username not in conv_cache:
            existing = [c for c in conv_repo.list_for_user(user.id, include_archived=True)
                        if c.title == LEGACY_TITLE]
            if existing:
                print(f"User {username}: legacy import already exists, skipping.")
                conv_cache[username] = ""
                continue
            conv_cache[username] = conv_repo.create(user.id, title=LEGACY_TITLE).id

        conv_id = conv_cache[username]
        if not conv_id:
            continue
        if row["user_msg"]:
            msg_repo.create(conv_id, user.id, "user", row["user_msg"],
                            intent=row["intent"] or "")
        if row["bot_reply"]:
            msg_repo.create(conv_id, user.id, "assistant", row["bot_reply"],
                            intent=row["intent"] or "")
        imported += 1

    print(f"Imported {imported} legacy rows.")
    return imported


if __name__ == "__main__":
    import_legacy()
