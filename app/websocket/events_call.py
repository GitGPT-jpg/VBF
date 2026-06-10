"""SocketIO call-mode events — fast, short voice replies."""
from __future__ import annotations

import threading

from flask import request
from flask_login import current_user

from app.services import chat_service
from app.utils.logger import get_logger

log = get_logger(__name__)


def register(socketio) -> None:
    @socketio.on("call_message")
    def handle_call(data):
        if not current_user.is_authenticated:
            return
        text = (data.get("text") or "").strip()
        req_id = (data.get("req_id") or "").strip()
        conversation_id = (data.get("conversation_id") or "").strip()
        if not text or not req_id:
            return

        user_id = current_user.id
        sid = request.sid

        def send(event: str, **payload) -> None:
            payload["req_id"] = req_id
            socketio.emit(event, payload, to=sid)

        def worker() -> None:
            try:
                send("status", key="status_call_processing", color="#FF6B9D")
                result = chat_service.run_chat_turn(
                    user_id, text, conversation_id=conversation_id,
                    mode_override="call", emit=send)
                send("call_reply", text=result.assistant_message.content,
                     audio_url=result.audio_url)
            except Exception as exc:  # noqa: BLE001
                log.error("call worker failed: %s", exc, exc_info=True)
            finally:
                send("call_done")

        threading.Thread(target=worker, daemon=True).start()
