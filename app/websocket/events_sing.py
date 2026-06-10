"""SocketIO singing events — song cards, async tasks, cancellation.

Flow:
    user asks to sing → match/intro (tts) → `song_card` {status: generating}
    → background RVC task → `song_ready` / `song_card` {status: failed}
Legacy events (`singing_start`, `song_ready`, `singing_end`) are kept so older
clients continue to work.
"""
from __future__ import annotations

import threading

from flask import request
from flask_login import current_user

from app.services import (
    conversation_service,
    message_service,
    singing_service,
    tts_service,
)
from app.utils.logger import get_logger

log = get_logger(__name__)

# req_id → task_id, so stop_singing can cancel the running render.
_req_tasks: dict[str, str] = {}
_req_tasks_lock = threading.Lock()

_SING_STOPWORDS = ["唱", "歌", "首", "一", "给我", "来", "个", "sing", "song", "听", "吧"]


def _extract_keyword(text: str) -> str:
    keyword = text
    for word in _SING_STOPWORDS:
        keyword = keyword.replace(word, "")
    return keyword.strip()


def run_sing_flow(socketio, user_id: str, text: str, req_id: str, sid: str,
                  conversation_id: str = "") -> None:
    """Execute the singing pipeline (called from the chat worker thread)."""

    def send(event: str, **payload) -> None:
        payload["req_id"] = req_id
        socketio.emit(event, payload, to=sid)

    conv = conversation_service.get_or_create(user_id, conversation_id)
    message_service.save_user_message(conv.id, user_id, text, intent="sing",
                                      state="singing")

    keyword = _extract_keyword(text)
    send("song_card", status="matching", title="")
    song = singing_service.match_song(keyword) if keyword else None
    if not song:
        song = singing_service.get_random_song()

    if not song:
        reply = "歌曲库还没准备好呢 🥺"
        msg = message_service.save_assistant_message(
            conv.id, user_id, reply, intent="sing_no_lib", state="idle")
        asset = tts_service.synthesize(reply, user_id, message_id=msg.id)
        send("bot_message", text=reply,
             audio_url=asset.public_url if asset else "", glow="pink",
             message_id=msg.id, conversation_id=conv.id)
        send("song_card", status="failed", title="")
        return

    title = song.get("title", "一首歌")
    intro = f"好，给你唱《{title}》~"
    intro_msg = message_service.save_assistant_message(
        conv.id, user_id, intro, intent="sing", state="singing")
    intro_asset = tts_service.synthesize(intro, user_id, message_id=intro_msg.id)
    send("bot_message", text=intro,
         audio_url=intro_asset.public_url if intro_asset else "", glow="pink",
         message_id=intro_msg.id, conversation_id=conv.id)
    send("singing_start", title=title)
    send("song_card", status="generating", title=title)
    send("status", key="status_singing", params={"title": title}, color="#8B7AA0")

    def on_done(task) -> None:
        with _req_tasks_lock:
            _req_tasks.pop(req_id, None)
        if task.status == "ready" and task.file_path:
            asset = tts_service.register_song_asset(
                user_id, task.file_path, title=title)
            url = asset.public_url if asset else ""
            song_msg = message_service.save_assistant_message(
                conv.id, user_id, f"🎵 《{title}》", content_type="song",
                intent="sing", state="idle",
                audio_asset_id=asset.id if asset else "",
                metadata={"title": title, "task_id": task.task_id})
            send("song_ready", audio_url=url, title=title,
                 message_id=song_msg.id, conversation_id=conv.id)
            send("song_card", status="ready", title=title, audio_url=url)
        elif task.status == "cancelled":
            send("song_card", status="cancelled", title=title)
        else:
            err = "嗓子有点不舒服…下次再唱给你听 🥺"
            err_msg = message_service.save_assistant_message(
                conv.id, user_id, err, intent="sing_fail", state="idle")
            err_asset = tts_service.synthesize(err, user_id, message_id=err_msg.id)
            send("singing_end")
            send("song_card", status="failed", title=title)
            send("bot_message", text=err,
                 audio_url=err_asset.public_url if err_asset else "", glow="pink",
                 message_id=err_msg.id, conversation_id=conv.id)

    task = singing_service.start_singing_task(user_id, song, on_done=on_done)
    with _req_tasks_lock:
        _req_tasks[req_id] = task.task_id


def register(socketio) -> None:
    @socketio.on("stop_singing")
    def on_stop(data):
        if not current_user.is_authenticated:
            return
        req_id = (data.get("req_id") or "").strip()
        if not req_id:
            return
        with _req_tasks_lock:
            task_id = _req_tasks.pop(req_id, None)
        if task_id:
            singing_service.cancel_singing_task(task_id, current_user.id)

    @socketio.on("singing_stopped")
    def on_singing_stopped(data):
        """After the user stops a song, the AI gently asks why."""
        if not current_user.is_authenticated:
            return
        req_id = (data.get("req_id") or "").strip()
        if not req_id:
            return
        user_id = current_user.id
        sid = request.sid

        def send(event: str, **payload) -> None:
            payload["req_id"] = req_id
            socketio.emit(event, payload, to=sid)

        def worker() -> None:
            try:
                from app.services import chat_service
                result = chat_service.run_chat_turn(
                    user_id,
                    "（你刚才在唱歌，对方把歌停了。请用20字以内、可爱又有一点点委屈的"
                    "语气问问：是唱得不好听吗？还是想换首歌呀？）",
                    emit=send)
                send("bot_message", text=result.assistant_message.content,
                     audio_url=result.audio_url, glow="pink",
                     message_id=result.assistant_message.id,
                     conversation_id=result.assistant_message.conversation_id)
            except Exception as exc:  # noqa: BLE001
                log.error("singing_stopped worker failed: %s", exc)
            finally:
                send("server_done")

        threading.Thread(target=worker, daemon=True).start()
