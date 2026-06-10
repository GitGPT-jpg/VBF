"""EmotionAnalyzer — lightweight rule-based emotional state estimation.

Used to keep `user_states.emotional_state` fresh and to inform the
PromptBuilder. Intentionally cheap (no LLM call per message).
"""
from __future__ import annotations

_EMOTION_RULES: list[tuple[str, list[str]]] = [
    ("sad", ["难过", "想哭", "哭了", "委屈", "失落", "心碎", "sad", "cry"]),
    ("anxious", ["焦虑", "紧张", "压力", "担心", "害怕", "anxious", "nervous", "worried"]),
    ("tired", ["好累", "心累", "疲惫", "没力气", "撑不住", "tired", "exhausted"]),
    ("lonely", ["孤独", "寂寞", "没人", "一个人", "lonely", "alone"]),
    ("angry", ["生气", "气死", "烦死", "讨厌", "angry", "mad", "annoyed"]),
    ("happy", ["开心", "高兴", "太好了", "哈哈", "好棒", "happy", "great", "yay"]),
    ("loving", ["想你", "爱你", "亲亲", "抱抱", "miss you", "love you"]),
]


def analyze(text: str) -> str:
    """Return an emotional state label, or 'neutral'."""
    t = (text or "").lower()
    for label, keywords in _EMOTION_RULES:
        if any(kw in t for kw in keywords):
            return label
    return "neutral"


def needs_comfort(emotion: str) -> bool:
    return emotion in ("sad", "anxious", "tired", "lonely", "angry")
