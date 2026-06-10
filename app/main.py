"""Application factory — wires config, DB, blueprints, sockets together.

Entry points:
    python web_app.py     (legacy-compatible)
    python -m app.main
"""
from __future__ import annotations

import os
import secrets
import sys
import threading

# UTF-8-safe console on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from flask import Blueprint, Flask, render_template
from flask_login import LoginManager, current_user, login_required
from flask_socketio import SocketIO

from app.config.settings import settings
from app.repositories.db import init_db
from app.services import safety_service, user_service
from app.utils.logger import get_logger, setup_logging

log = get_logger(__name__)

pages = Blueprint("pages", __name__)


@pages.route("/")
@login_required
def index():
    return render_template("chat.html", username=current_user.display_name)


def create_app() -> tuple[Flask, SocketIO]:
    """Build the Flask app + SocketIO instance."""
    setup_logging(settings.log_level)
    safety_service.run_startup_checks()
    init_db()
    user_service.ensure_bootstrap_users()

    project_dir = settings.project_dir
    app = Flask(
        __name__,
        template_folder=os.path.join(project_dir, "templates"),
        static_folder=os.path.join(project_dir, "static"),
    )
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.secret_key = settings.web_secret_key or secrets.token_hex(32)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=settings.is_production,
        REMEMBER_COOKIE_HTTPONLY=True,
    )
    app.jinja_env.filters["basename"] = os.path.basename

    # ── auth ──
    login_manager = LoginManager(app)
    login_manager.login_view = "auth.login"

    from app.api.routes_auth import load_web_user

    @login_manager.user_loader
    def load_user(user_id: str):
        return load_web_user(user_id)

    # ── blueprints ──
    from app.api import routes_admin, routes_audio, routes_auth, routes_chat
    app.register_blueprint(pages)
    app.register_blueprint(routes_auth.bp)
    app.register_blueprint(routes_chat.bp)
    app.register_blueprint(routes_audio.bp)
    app.register_blueprint(routes_admin.bp)

    # ── sockets ──
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")
    from app.websocket import events_call, events_chat, events_presence, events_sing
    events_presence.register(socketio)
    events_chat.register(socketio)
    events_call.register(socketio)
    events_sing.register(socketio)

    return app, socketio


def _print_startup(port: int) -> None:
    """Background banner: local/LAN/ngrok URLs."""
    import re
    import socket as _socket
    import time as _time

    try:
        lan_ip = _socket.gethostbyname(_socket.gethostname())
    except OSError:
        lan_ip = "<本机IP>"

    print("\n💕 AI Companion Chat 启动")
    print(f"   本机:  http://localhost:{port}")
    print(f"   局域网: http://{lan_ip}:{port}")

    ngrok_log = os.path.join(settings.project_dir, "logs", "ngrok.log")
    ngrok_url = None
    for _ in range(20):
        if os.path.exists(ngrok_log):
            try:
                content = open(ngrok_log, encoding="utf-8", errors="replace").read()
                match = re.search(r"url=(https://\S+)", content)
                if match:
                    ngrok_url = match.group(1)
                    break
            except OSError:
                pass
        _time.sleep(1)
    print(f"   公网:  {ngrok_url or '（ngrok 未配置）'}\n")


def run() -> None:
    app, socketio = create_app()
    port = settings.web_port
    threading.Thread(target=_print_startup, args=(port,), daemon=True).start()
    socketio.run(app, host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    run()
