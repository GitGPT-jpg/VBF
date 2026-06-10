"""Admin routes — owner-only insight into conversations."""
from __future__ import annotations

from flask import Blueprint, abort, render_template
from flask_login import current_user, login_required

from app.repositories.db import get_conn

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/logs")
@login_required
def logs():
    if current_user.role != "owner":
        abort(403)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT m.created_at AS ts, u.username, m.intent,"
            " CASE WHEN m.role = 'user' THEN m.content ELSE '' END AS user_msg,"
            " CASE WHEN m.role = 'assistant' THEN m.content ELSE '' END AS bot_reply,"
            " '' AS audio_path"
            " FROM messages m JOIN users u ON u.id = m.user_id"
            " ORDER BY m.created_at DESC LIMIT 500").fetchall()
        total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        users = [r[0] for r in conn.execute(
            "SELECT DISTINCT username FROM users ORDER BY username")]
        sing_count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE intent = 'sing'").fetchone()[0]
    return render_template("logs.html", rows=rows, total=total,
                           users=users, sing_count=sing_count)
