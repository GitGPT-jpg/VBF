"""DialogStateMachine — explicit conversation lifecycle states.

States and events are pushed to the frontend via SocketIO (`dialog_state`
event) and persisted in `user_states`.
"""
from __future__ import annotations

from typing import Callable

from app.utils.logger import get_logger

log = get_logger(__name__)

STATES = [
    "idle", "listening", "thinking", "speaking", "generating_voice",
    "singing", "interrupted", "sleep_mode", "call_mode", "error",
]

EVENTS = [
    "user_message_received", "llm_started", "llm_delta", "llm_finished",
    "tts_started", "tts_finished", "audio_playing", "user_interrupt",
    "sing_started", "sing_finished", "sleep_enabled", "sleep_disabled",
    "call_enabled", "call_disabled", "error_occurred", "reset",
]

# (current_state, event) -> next_state. '*' matches any current state.
_TRANSITIONS: dict[tuple[str, str], str] = {
    ("*", "error_occurred"): "error",
    ("*", "reset"): "idle",
    ("*", "user_interrupt"): "interrupted",
    ("*", "sleep_enabled"): "sleep_mode",
    ("*", "call_enabled"): "call_mode",
    ("sleep_mode", "sleep_disabled"): "idle",
    ("call_mode", "call_disabled"): "idle",

    ("idle", "user_message_received"): "thinking",
    ("interrupted", "user_message_received"): "thinking",
    ("error", "user_message_received"): "thinking",
    ("speaking", "user_message_received"): "thinking",
    ("listening", "user_message_received"): "thinking",
    ("sleep_mode", "user_message_received"): "thinking",
    ("call_mode", "user_message_received"): "thinking",

    ("thinking", "llm_started"): "thinking",
    ("thinking", "llm_delta"): "speaking",
    ("speaking", "llm_delta"): "speaking",
    ("thinking", "llm_finished"): "speaking",
    ("speaking", "llm_finished"): "speaking",

    ("speaking", "tts_started"): "generating_voice",
    ("thinking", "tts_started"): "generating_voice",
    ("generating_voice", "tts_finished"): "speaking",
    ("speaking", "audio_playing"): "speaking",

    ("thinking", "sing_started"): "singing",
    ("speaking", "sing_started"): "singing",
    ("singing", "sing_finished"): "idle",
}


class InvalidTransition(Exception):
    pass


class DialogStateMachine:
    """Per-user dialog state machine with observer callbacks."""

    def __init__(self, initial: str = "idle",
                 on_change: Callable[[str, str, str], None] | None = None,
                 strict: bool = False) -> None:
        if initial not in STATES:
            raise ValueError(f"unknown state: {initial}")
        self.state = initial
        self._on_change = on_change
        self._strict = strict

    def dispatch(self, event: str) -> str:
        """Apply an event; returns the (possibly unchanged) new state."""
        if event not in EVENTS:
            raise ValueError(f"unknown event: {event}")
        nxt = _TRANSITIONS.get((self.state, event)) or _TRANSITIONS.get(("*", event))
        if nxt is None:
            if self._strict:
                raise InvalidTransition(f"{self.state} --{event}-> ?")
            log.debug("Ignored event %s in state %s", event, self.state)
            return self.state
        if nxt != self.state:
            old = self.state
            self.state = nxt
            if self._on_change:
                try:
                    self._on_change(old, nxt, event)
                except Exception as exc:  # noqa: BLE001
                    log.warning("state on_change callback failed: %s", exc)
        return self.state

    def can(self, event: str) -> bool:
        return ((self.state, event) in _TRANSITIONS) or (("*", event) in _TRANSITIONS)
