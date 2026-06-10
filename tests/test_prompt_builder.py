"""PromptBuilder tests — layered sections and mode rules."""
from app.agents.prompt_builder import PromptContext, build_system_prompt
from app.models.schemas import Memory


def _memory(mid: str, mtype: str, content: str, importance: int = 3) -> Memory:
    return Memory(id=mid, user_id="u1", memory_type=mtype, content=content,
                  importance=importance)


def test_persona_section_present():
    prompt = build_system_prompt(PromptContext(mode="normal"))
    assert "小宇" in prompt
    assert "边界规则" in prompt


def test_sleep_mode_rules():
    prompt = build_system_prompt(PromptContext(mode="sleep"))
    assert "哄对方入睡" in prompt
    assert "不要向对方提问" in prompt


def test_call_mode_rules():
    prompt = build_system_prompt(PromptContext(mode="call"))
    assert "打电话" in prompt
    assert "20 字" in prompt


def test_memory_recall_honesty_rule():
    prompt = build_system_prompt(PromptContext(mode="memory_recall"))
    assert "不要编造" in prompt


def test_memories_injected_and_deduped():
    mem = _memory("m1", "preference", "她喜欢周杰伦的歌")
    ctx = PromptContext(mode="normal", relevant_memories=[mem],
                        recent_memories=[mem], important_memories=[mem])
    prompt = build_system_prompt(ctx)
    assert prompt.count("她喜欢周杰伦的歌") == 1


def test_emotion_and_user_context():
    ctx = PromptContext(mode="comfort", user_display_name="小美",
                        emotional_state="sad")
    prompt = build_system_prompt(ctx)
    assert "小美" in prompt
    assert "sad" in prompt
    assert "共情" in prompt


def test_flirt_policy_bounds():
    prompt = build_system_prompt(PromptContext(mode="flirt"))
    assert "不油腻" in prompt
