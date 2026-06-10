"""ChatService — the orchestrator for one chat turn.

Pipeline:
    intent → emotion → persist user msg → prompt build (memories injected)
    → LLM (streaming) → persist assistant msg → TTS asset → memory extraction

The websocket layer supplies an `emitter` implementing the streaming events
(assistant_message_start/delta/done/error + dialog_state) so this module
stays transport-agnostic and testable.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from app.agents import emotion_analyzer, memory_retriever
from app.agents.dialog_state_machine import DialogStateMachine
from app.agents.intent_router import IntentRouter
from app.agents.prompt_builder import PromptContext, build_system_prompt
from app.agents.response_policy import get_policy, mode_for_intent
from app.config.settings import settings
from app.models.schemas import IntentResult, Message
from app.services import (
    conversation_service,
    memory_service,
    message_service,
    tts_service,
    user_service,
)
from app.services.llm_service import llm_service
from app.utils.logger import get_logger

log = get_logger(__name__)

intent_router = IntentRouter(llm_service=llm_service)

_FALLBACKS = {
    "sleep": "嗯…我在呢……慢慢闭上眼睛……",
    "call": "嗯…我在听呢……",
    "default": "嗯……我刚没听清，再说一遍？",
}


class Emitter(Protocol):
    def __call__(self, event: str, **payload: Any) -> None: ...


@dataclass
class TurnResult:
    user_message: Message
    assistant_message: Message
    intent: IntentResult
    mode: str
    audio_url: str = ""


def _noop_emitter(event: str, **payload: Any) -> None:  # pragma: no cover
    pass


def run_chat_turn(user_id: str, text: str, conversation_id: str = "",
                  mode_override: str = "", emit: Emitter | None = None,
                  generate_voice: bool = True) -> TurnResult:
    """Execute a full chat turn. Streaming events go through `emit`."""
    emit = emit or _noop_emitter

    user = user_service.get_user(user_id)
    display_name = user.display_name if user else ""

    conv = conversation_service.get_or_create(user_id, conversation_id)

    # ── 1. intent + emotion + state ──
    intent = intent_router.route(text)
    emotion = emotion_analyzer.analyze(text)
    mode = mode_override or mode_for_intent(intent.intent)
    if emotion_analyzer.needs_comfort(emotion) and mode == "normal":
        mode = "comfort"
    policy = get_policy(mode)

    state = user_service.get_state(user_id)
    machine = DialogStateMachine(
        initial=state.dialog_state if state.dialog_state in ("sleep_mode", "call_mode") else "idle",
        on_change=lambda old, new, ev: emit(
            "dialog_state", state=new, previous=old, event=ev))
    machine.dispatch("user_message_received")
    state.emotional_state = emotion
    state.sleep_mode_enabled = mode == "sleep"
    state.call_mode_enabled = mode == "call"

    # ── 2. persist user message ──
    user_msg = message_service.save_user_message(
        conv.id, user_id, text, intent=intent.intent, state=machine.state)
    conversation_service.maybe_autotitle(conv, text)

    # ── 3. build prompt ──
    ctx = PromptContext(
        mode=mode, intent=intent.intent, user_display_name=display_name,
        emotional_state=emotion,
        relevant_memories=memory_service.retrieve_memories(text, user_id, top_k=5),
        recent_memories=memory_retriever.recent_memories(user_id, days=3, limit=5),
        important_memories=memory_retriever.important_memories(user_id, limit=5),
    )
    system = build_system_prompt(ctx)
    history = message_service.llm_history(conv.id, max_turns=10)

    # ── 4. LLM (streaming) ──
    machine.dispatch("llm_started")
    emit("assistant_message_start", conversation_id=conv.id, mode=mode,
         intent=intent.intent)

    reply = ""
    try:
        if settings.enable_streaming:
            first = True
            for chunk in llm_service.stream(system, history, policy.max_tokens):
                if first:
                    machine.dispatch("llm_delta")
                    first = False
                reply += chunk
                emit("assistant_message_delta", conversation_id=conv.id, delta=chunk)
        else:
            reply = llm_service.complete(system, history, policy.max_tokens)
        reply = reply.strip()
        if not reply:
            raise ValueError("empty LLM reply")
        machine.dispatch("llm_finished")
    except Exception as exc:  # noqa: BLE001
        log.warning("LLM turn failed: %s", exc)
        machine.dispatch("error_occurred")
        reply = _FALLBACKS.get(mode, _FALLBACKS["default"])
        emit("assistant_message_error",
             conversation_id=conv.id, fallback=reply)
        machine.dispatch("reset")

    # ── 5. persist assistant message ──
    assistant_msg = message_service.save_assistant_message(
        conv.id, user_id, reply, intent=intent.intent, state=machine.state,
        metadata={"mode": mode, "emotion": emotion})

    # ── 6. TTS ──
    audio_url = ""
    if generate_voice and policy.generate_voice:
        machine.dispatch("tts_started")
        emit("dialog_state", state="generating_voice", previous=machine.state,
             event="tts_started")
        asset = tts_service.synthesize(reply, user_id, message_id=assistant_msg.id,
                                       slow=(mode == "sleep"))
        if asset:
            audio_url = asset.public_url
            from app.repositories import message_repository as msg_repo
            msg_repo.set_audio_asset(assistant_msg.id, asset.id)
            assistant_msg.audio_asset_id = asset.id
        machine.dispatch("tts_finished")

    emit("assistant_message_done",
         conversation_id=conv.id,
         message=message_service.serialize(assistant_msg) | {"audio_url": audio_url},
         mode=mode, intent=intent.intent)

    # ── 7. persist final state + async memory extraction ──
    if mode not in ("sleep", "call"):
        machine.dispatch("reset")
    state.dialog_state = machine.state
    user_service.save_state(state)

    if settings.enable_memory_extraction:
        threading.Thread(
            target=memory_service.extract_memories,
            args=(user_id, text, reply, user_msg.id),
            daemon=True).start()

    return TurnResult(user_message=user_msg, assistant_message=assistant_msg,
                      intent=intent, mode=mode, audio_url=audio_url)
