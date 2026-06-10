"""SocketIO chat events — streaming AI replies.

Events emitted to the client (all carry req_id):
    dialog_state             {state, previous, event}
    assistant_message_start  {conversation_id, mode, intent}
    assistant_message_delta  {conversation_id, delta}
    assistant_message_done   {conversation_id, message{...}, mode, intent}
    assistant_message_error  {conversation_id, fallback}
    status / bot_message / server_done   (legacy compatibility)
"""
from __future__ import annotations

import threading

from flask import request
from flask_login import current_user

from app.services import chat_service
from app.utils.logger import get_logger
from app.websocket import events_sing

log = get_logger(__name__)


def register(socketio) -> None:
    @socketio.on("chat_message")
    def handle_chat(data):
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
                send("status", key="status_thinking", color="#8B7AA0")
                intent = chat_service.intent_router.route(text)
                if intent.intent == "sing":
                    events_sing.run_sing_flow(
                        socketio, user_id, text, req_id, sid, conversation_id)
                    return

                result = chat_service.run_chat_turn(
                    user_id, text, conversation_id=conversation_id, emit=send)
                # Legacy-compatible final event (old clients render bot_message).
                glow = "purple" if result.mode == "sleep" else "pink"
                send("bot_message", text=result.assistant_message.content,
                     audio_url=result.audio_url, glow=glow,
                     message_id=result.assistant_message.id,
                     conversation_id=result.assistant_message.conversation_id)
            except Exception as exc:  # noqa: BLE001
                log.error("chat worker failed: %s", exc, exc_info=True)
                send("assistant_message_error", conversation_id=conversation_id,
                     fallback="嗯……我刚走神了，再说一遍好吗？")
            finally:
                send("server_done")

        threading.Thread(target=worker, daemon=True).start()
