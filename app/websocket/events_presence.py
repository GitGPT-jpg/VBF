"""SocketIO presence events — connect/disconnect + state sync."""
from __future__ import annotations

from flask import request
from flask_login import current_user

from app.services import user_service
from app.utils.logger import get_logger

log = get_logger(__name__)


def register(socketio) -> None:
    @socketio.on("connect")
    def on_connect():
        if not current_user.is_authenticated:
            return False  # reject anonymous sockets
        state = user_service.get_state(current_user.id)
        socketio.emit("presence", {
            "online": True,
            "dialog_state": state.dialog_state,
            "emotional_state": state.emotional_state,
            "sleep_mode": state.sleep_mode_enabled,
            "call_mode": state.call_mode_enabled,
        }, to=request.sid)
        log.info("socket connected: %s", current_user.username)

    @socketio.on("disconnect")
    def on_disconnect():
        if current_user.is_authenticated:
            log.info("socket disconnected: %s", current_user.username)
