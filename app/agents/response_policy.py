"""ResponsePolicy — declarative knobs for how the AI should reply per mode."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponsePolicy:
    mode: str
    max_sentences: int = 3
    max_tokens: int = 160
    may_ask_question: bool = True
    should_comfort: bool = False
    may_flirt: bool = False
    may_advise: bool = True
    generate_voice: bool = True
    style_hint: str = ""


_POLICIES: dict[str, ResponsePolicy] = {
    "normal": ResponsePolicy(
        mode="normal", max_sentences=3, max_tokens=160, may_ask_question=True,
        may_flirt=False, may_advise=True,
        style_hint="温柔自然、简短，2-3 句，可以轻微幽默。"),
    "comfort": ResponsePolicy(
        mode="comfort", max_sentences=3, max_tokens=180, may_ask_question=False,
        should_comfort=True, may_advise=False,
        style_hint="先共情后陪伴，不急着讲道理，不连续追问，可以承认对方的情绪。"),
    "sleep": ResponsePolicy(
        mode="sleep", max_sentences=2, max_tokens=80, may_ask_question=False,
        may_advise=False,
        style_hint="极短、缓慢、多用……停顿，不提问，不提供刺激性信息。"),
    "call": ResponsePolicy(
        mode="call", max_sentences=2, max_tokens=60, may_ask_question=False,
        may_advise=False,
        style_hint="1-2 句、不超过 20 字，像电话里实时回应，允许“嗯…”“我在呢”。"),
    "flirt": ResponsePolicy(
        mode="flirt", max_sentences=3, max_tokens=140, may_ask_question=True,
        may_flirt=True, may_advise=False,
        style_hint="轻微暧昧但不油腻、不越界、不低俗。"),
    "sing": ResponsePolicy(
        mode="sing", max_sentences=2, max_tokens=80, may_ask_question=True,
        may_advise=False, style_hint="先确认歌曲，再生成歌曲卡片。"),
    "memory_recall": ResponsePolicy(
        mode="memory_recall", max_sentences=3, max_tokens=180, may_ask_question=True,
        may_advise=False,
        style_hint="从记忆中检索回答；不确定时诚实说明，不要编造。"),
}


def get_policy(mode: str) -> ResponsePolicy:
    return _POLICIES.get(mode, _POLICIES["normal"])


def mode_for_intent(intent: str) -> str:
    """Map a routed intent to a response mode."""
    mapping = {
        "comfort": "comfort",
        "sleep": "sleep",
        "call": "call",
        "flirt": "flirt",
        "sing": "sing",
        "memory_recall": "memory_recall",
    }
    return mapping.get(intent, "normal")
