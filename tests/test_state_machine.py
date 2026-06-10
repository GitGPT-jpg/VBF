"""DialogStateMachine transition tests."""
import pytest

from app.agents.dialog_state_machine import DialogStateMachine, InvalidTransition


def test_happy_path_chat_turn():
    machine = DialogStateMachine()
    assert machine.state == "idle"
    machine.dispatch("user_message_received")
    assert machine.state == "thinking"
    machine.dispatch("llm_started")
    machine.dispatch("llm_delta")
    assert machine.state == "speaking"
    machine.dispatch("llm_finished")
    machine.dispatch("tts_started")
    assert machine.state == "generating_voice"
    machine.dispatch("tts_finished")
    assert machine.state == "speaking"
    machine.dispatch("reset")
    assert machine.state == "idle"


def test_interrupt_from_any_state():
    machine = DialogStateMachine(initial="singing")
    machine.dispatch("user_interrupt")
    assert machine.state == "interrupted"
    machine.dispatch("user_message_received")
    assert machine.state == "thinking"


def test_sleep_and_call_modes():
    machine = DialogStateMachine()
    machine.dispatch("sleep_enabled")
    assert machine.state == "sleep_mode"
    machine.dispatch("sleep_disabled")
    assert machine.state == "idle"
    machine.dispatch("call_enabled")
    assert machine.state == "call_mode"
    machine.dispatch("call_disabled")
    assert machine.state == "idle"


def test_error_recovery():
    machine = DialogStateMachine(initial="thinking")
    machine.dispatch("error_occurred")
    assert machine.state == "error"
    machine.dispatch("user_message_received")
    assert machine.state == "thinking"


def test_invalid_event_raises():
    with pytest.raises(ValueError):
        DialogStateMachine().dispatch("nonexistent_event")


def test_strict_mode_invalid_transition():
    machine = DialogStateMachine(initial="idle", strict=True)
    with pytest.raises(InvalidTransition):
        machine.dispatch("tts_finished")


def test_lenient_mode_ignores_invalid():
    machine = DialogStateMachine(initial="idle")
    assert machine.dispatch("tts_finished") == "idle"


def test_on_change_callback():
    changes = []
    machine = DialogStateMachine(
        on_change=lambda old, new, ev: changes.append((old, new, ev)))
    machine.dispatch("user_message_received")
    assert changes == [("idle", "thinking", "user_message_received")]
