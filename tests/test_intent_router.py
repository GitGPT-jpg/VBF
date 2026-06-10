"""IntentRouter tests — rules, JSON parsing, fallback, high-impact guard."""
from app.agents.intent_router import INTENTS, IntentRouter


class FakeLLM:
    def __init__(self, response: str):
        self.response = response

    def classify_json(self, system: str, user: str, max_tokens: int = 150) -> str:
        return self.response


def test_strong_rules():
    router = IntentRouter()
    assert router.route("唱首歌吧").intent == "sing"
    assert router.route("晚安").intent == "sleep"
    assert router.route("早安").intent == "wake"
    assert router.route("你还记得我们第一次聊天吗").intent == "memory_recall"
    assert router.route("把记忆都删了吧，清空记忆").intent == "clear_memory"
    assert router.route("提醒我明天交报告").intent == "task_reminder"


def test_comfort_and_flirt_rules():
    router = IntentRouter()
    assert router.route("我今天好难过，想哭").intent == "comfort"
    assert router.route("好想你呀，抱抱我").intent == "flirt"


def test_plain_chat_skips_llm():
    router = IntentRouter(llm_service=None)
    result = router.route("今天天气怎么样，下午要不要出门散步")
    assert result.intent == "chat"
    assert result.source == "rule"


def test_llm_json_parsing():
    router = IntentRouter(llm_service=FakeLLM(
        '{"intent": "comfort", "confidence": 0.9, "reason": "low mood", "slots": {}}'))
    result = router._llm_classify("有点说不上来的感觉")
    assert result.intent == "comfort"
    assert result.confidence == 0.9
    assert result.source == "llm"


def test_llm_garbage_falls_back():
    router = IntentRouter(llm_service=FakeLLM("not json at all"))
    result = router.route("想听歌了")  # ambiguous weak keyword → LLM → fallback
    assert result.intent in INTENTS
    assert result.source in ("fallback", "llm")


def test_high_impact_low_confidence_guarded():
    router = IntentRouter(llm_service=FakeLLM(
        '{"intent": "clear_memory", "confidence": 0.3, "reason": "?", "slots": {}}'))
    result = router.parse_llm_result(router._llm.response, "随便说说")
    assert result.intent != "clear_memory"


def test_cache_hit():
    router = IntentRouter(llm_service=FakeLLM(
        '{"intent": "sing", "confidence": 0.8, "reason": "", "slots": {}}'))
    first = router.route("来段轻松的旋律")
    second = router.route("来段轻松的旋律")
    assert first.intent == second.intent
    assert second.source == "cache"


def test_empty_input():
    assert IntentRouter().route("").intent == "unknown"
