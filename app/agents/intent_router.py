"""IntentRouter — hybrid rule + LLM intent classification.

Strategy:
1. High-confidence rules first (fast path, no LLM cost).
2. Ambiguous inputs go to LLM classification (strict JSON output).
3. TTL cache to avoid repeated LLM calls.
4. Rule-based fallback when LLM is unavailable.
5. High-impact intents (sing / sleep / clear_memory) require strong signals.
"""
from __future__ import annotations

import json
import re
import time

from app.models.schemas import IntentResult
from app.utils.logger import get_logger

log = get_logger(__name__)

INTENTS = [
    "chat", "comfort", "sleep", "wake", "call", "sing", "flirt",
    "memory_recall", "preference_update", "clear_memory", "daily_checkin",
    "task_reminder", "small_talk", "unknown",
]

# High-impact intents: never inferred from weak signals alone.
HIGH_IMPACT = {"sing", "sleep", "clear_memory", "call"}

_STRONG_RULES: list[tuple[str, list[str]]] = [
    ("clear_memory", ["清空记忆", "删除记忆", "忘掉我", "把记忆都删", "forget everything",
                      "clear my memory", "清除记忆"]),
    ("sing", ["唱首歌", "唱一个", "唱首", "唱支歌", "来一首", "唱来听听", "唱给我听",
              "唱首歌吧", "sing a song", "sing me", "sing for me"]),
    ("sleep", ["晚安", "睡了", "先睡了", "我睡了", "哄我睡", "哄我睡觉",
               "good night", "night night"]),
    ("wake", ["早安", "早上好", "起床了", "醒了", "不睡了", "good morning"]),
    ("call", ["打电话", "打个电话", "语音通话", "通话模式", "call me", "voice call"]),
    ("memory_recall", ["你还记得", "你记得吗", "还记得我", "记不记得",
                       "do you remember", "remember when"]),
    ("daily_checkin", ["今天过得", "日常打卡", "每日签到", "daily check"]),
]

_COMFORT_HINTS = ["难过", "想哭", "哭了", "委屈", "压力好大", "好烦", "心情不好",
                  "焦虑", "崩溃", "好难受", "心累", "emo", "失眠", "孤独", "寂寞",
                  "sad", "depressed", "anxious", "upset"]
_FLIRT_HINTS = ["想你", "亲亲", "抱抱", "么么", "爱你", "撒娇", "miss you",
                "love you", "hug me", "kiss"]
_PREFERENCE_HINTS = ["以后叫我", "记住我喜欢", "我喜欢你叫我", "别叫我",
                     "我不喜欢你", "remember i like", "call me"]
_TASK_HINTS = ["提醒我", "记得提醒", "别忘了提醒", "remind me"]

_SING_WEAK = ["唱", "歌", "sing", "song", "听歌", "来段"]
_SLEEP_WEAK = ["睡", "困", "累", "sleep", "休息", "疲惫"]

_CACHE_TTL_SEC = 30


class IntentRouter:
    """Classify user text into one of INTENTS, returning IntentResult."""

    def __init__(self, llm_service=None) -> None:
        # llm_service is injected to keep this module testable without network.
        self._llm = llm_service
        self._cache: dict[str, tuple[float, IntentResult]] = {}

    # ── public API ──────────────────────────────────────────────────────────
    def route(self, text: str) -> IntentResult:
        text = (text or "").strip()
        if not text:
            return IntentResult(intent="unknown", confidence=0.0, source="rule")

        rule = self._rule_match(text)
        if rule is not None:
            return rule

        cached = self._cache_get(text)
        if cached is not None:
            return cached

        result = self._llm_classify(text)
        self._cache_put(text, result)
        return result

    # ── rules ───────────────────────────────────────────────────────────────
    def _rule_match(self, text: str) -> IntentResult | None:
        t = text.lower()

        for intent, keywords in _STRONG_RULES:
            for kw in keywords:
                if kw in t:
                    return IntentResult(intent=intent, confidence=0.95,
                                        reason=f"strong keyword: {kw}", source="rule")

        if any(kw in t for kw in _TASK_HINTS):
            return IntentResult(intent="task_reminder", confidence=0.85,
                                reason="task hint", source="rule")
        if any(kw in t for kw in _PREFERENCE_HINTS):
            return IntentResult(intent="preference_update", confidence=0.8,
                                reason="preference hint", source="rule")
        if any(kw in t for kw in _COMFORT_HINTS):
            return IntentResult(intent="comfort", confidence=0.8,
                                reason="emotion hint", source="rule")
        if any(kw in t for kw in _FLIRT_HINTS):
            return IntentResult(intent="flirt", confidence=0.75,
                                reason="affection hint", source="rule")

        # Nothing song/sleep-ish at all → plain chat; skip LLM cost.
        if not any(kw in t for kw in _SING_WEAK + _SLEEP_WEAK):
            if len(text) <= 6 and re.fullmatch(r"[\u4e00-\u9fffA-Za-z\s?？!！。.…~]+", text):
                return IntentResult(intent="small_talk", confidence=0.7,
                                    reason="short greeting-like text", source="rule")
            return IntentResult(intent="chat", confidence=0.7,
                                reason="no special signals", source="rule")
        return None  # ambiguous → LLM

    # ── LLM classification ───────────────────────────────────────────────────
    def _llm_classify(self, text: str) -> IntentResult:
        if self._llm is None:
            return self._fallback(text)
        try:
            raw = self._llm.classify_json(
                system=("你是一个意图分类器。只输出 JSON，不要输出其他内容。格式："
                        '{"intent": "...", "confidence": 0.0, "reason": "...", "slots": {}}'
                        f"\nintent 必须是其中之一：{', '.join(INTENTS)}"),
                user=("分类规则：\n"
                      "- sing：想听唱歌；sleep：想被哄睡/说困了；wake：刚醒/早安\n"
                      "- comfort：情绪低落需要安慰；flirt：撒娇/表达爱意\n"
                      "- memory_recall：问你是否记得某事；preference_update：告诉你 TA 的偏好\n"
                      "- clear_memory：要求删除记忆；task_reminder：要求提醒\n"
                      "- daily_checkin：汇报今天过得怎样；small_talk：寒暄；chat：普通聊天\n"
                      f"用户说：「{text}」"),
                max_tokens=150,
            )
            return self.parse_llm_result(raw, text)
        except Exception as exc:  # noqa: BLE001
            log.warning("Intent LLM failed (%s); using rule fallback", exc)
            return self._fallback(text)

    def parse_llm_result(self, raw: str, text: str) -> IntentResult:
        """Parse strict-JSON LLM output; tolerate wrapping text; fallback on garbage."""
        try:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            data = json.loads(match.group(0) if match else raw)
            intent = str(data.get("intent", "unknown")).strip().lower()
            confidence = float(data.get("confidence", 0.0))
            if intent not in INTENTS:
                intent = "unknown"
            # Guard high-impact intents against low-confidence LLM guesses.
            if intent in HIGH_IMPACT and confidence < 0.6:
                return self._fallback(text)
            return IntentResult(
                intent=intent, confidence=confidence,
                reason=str(data.get("reason", "")),
                slots=data.get("slots") or {}, source="llm")
        except (json.JSONDecodeError, ValueError, AttributeError, TypeError):
            return self._fallback(text)

    # ── fallback ─────────────────────────────────────────────────────────────
    def _fallback(self, text: str) -> IntentResult:
        t = text.lower()
        if any(kw in t for kw in _SING_WEAK):
            return IntentResult(intent="sing", confidence=0.5,
                                reason="weak keyword fallback", source="fallback")
        if any(kw in t for kw in _SLEEP_WEAK):
            return IntentResult(intent="sleep", confidence=0.5,
                                reason="weak keyword fallback", source="fallback")
        return IntentResult(intent="chat", confidence=0.4,
                            reason="default fallback", source="fallback")

    # ── cache ────────────────────────────────────────────────────────────────
    def _cache_get(self, text: str) -> IntentResult | None:
        key = text.lower()[:60]
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < _CACHE_TTL_SEC:
            result = hit[1]
            return IntentResult(intent=result.intent, confidence=result.confidence,
                                reason=result.reason, slots=result.slots, source="cache")
        return None

    def _cache_put(self, text: str, result: IntentResult) -> None:
        self._cache[text.lower()[:60]] = (time.time(), result)
        if len(self._cache) > 500:
            self._cache.clear()
