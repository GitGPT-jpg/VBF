"""MemoryService — LLM structured memory extraction + lifecycle management.

Memory types: profile / preference / episodic / emotional / relationship / task

Extraction contract (LLM must output strict JSON):
{
  "should_remember": true,
  "memories": [
    {"type": "emotional", "content": "...", "importance": 4, "confidence": 0.86}
  ]
}
Low-confidence items are dropped; duplicates raise importance instead of
creating new rows.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.agents import memory_retriever
from app.config.settings import settings
from app.models.schemas import ExtractedMemory, Memory
from app.repositories import memory_repository as memory_repo
from app.utils.logger import get_logger
from app.utils.time import days_ago_iso

log = get_logger(__name__)

VALID_TYPES = {"profile", "preference", "episodic", "emotional", "relationship", "task"}
MIN_CONFIDENCE = 0.6

_EXTRACT_SYSTEM = (
    "你是一个记忆提取器。从对话中提取值得长期记住的用户信息。\n"
    "只输出 JSON，不要输出其他内容。格式：\n"
    '{"should_remember": true, "memories": [{"type": "emotional", '
    '"content": "...", "importance": 4, "confidence": 0.86}]}\n'
    "type 取值：profile（名字/生日/身份）、preference（喜好/称呼习惯）、"
    "episodic（发生的事）、emotional（情绪状态）、relationship（互动习惯/纪念日/边界）、"
    "task（提醒/计划）。\n"
    "importance 为 1-5；confidence 为 0-1。\n"
    "没有值得记的就输出 {\"should_remember\": false, \"memories\": []}。"
    "不要提取闲聊、客套话或 AI 自己说的话。"
)


def parse_extraction(raw: str) -> list[ExtractedMemory]:
    """Parse the LLM extraction JSON; tolerant of wrapping text."""
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(match.group(0) if match else raw)
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []
    if not data.get("should_remember"):
        return []
    result: list[ExtractedMemory] = []
    for item in data.get("memories", []):
        try:
            mtype = str(item.get("type", "")).strip().lower()
            content = str(item.get("content", "")).strip()
            importance = int(item.get("importance", 3))
            confidence = float(item.get("confidence", 0.5))
        except (ValueError, TypeError, AttributeError):
            continue
        if mtype not in VALID_TYPES or not content:
            continue
        if confidence < MIN_CONFIDENCE:
            continue
        result.append(ExtractedMemory(
            type=mtype, content=content[:300],
            importance=max(1, min(5, importance)),
            confidence=max(0.0, min(1.0, confidence))))
    return result


def extract_memories(user_id: str, user_message: str, assistant_reply: str,
                     source_message_id: str = "", llm=None) -> list[Memory]:
    """Run LLM extraction over one exchange and persist results."""
    if not settings.enable_memory_extraction:
        return []
    if llm is None:
        from app.services.llm_service import llm_service as llm
    try:
        raw = llm.classify_json(
            system=_EXTRACT_SYSTEM,
            user=f"用户说：{user_message}\nAI 回复：{assistant_reply}",
            max_tokens=400)
    except Exception as exc:  # noqa: BLE001
        log.warning("memory extraction LLM failed: %s", exc)
        return []
    saved: list[Memory] = []
    for em in parse_extraction(raw):
        saved_mem = save_memory(user_id, em.type, em.content, em.importance,
                                em.confidence, source_message_id)
        if saved_mem:
            saved.append(saved_mem)
    if saved:
        log.info("Extracted %d memories for user %s", len(saved), user_id)
    return saved


def save_memory(user_id: str, memory_type: str, content: str, importance: int = 3,
                confidence: float = 0.8, source_message_id: str = "") -> Memory | None:
    """Persist a memory; duplicates bump importance instead of duplicating."""
    dup = memory_repo.find_duplicate(user_id, memory_type, content)
    if dup:
        memory_repo.update(dup.id, user_id,
                           importance=min(5, dup.importance + 1),
                           confidence=max(dup.confidence, confidence))
        return None
    return memory_repo.create(user_id, memory_type, content, importance,
                              confidence, source_message_id)


def retrieve_memories(query: str, user_id: str, top_k: int = 6) -> list[Memory]:
    return memory_retriever.retrieve(user_id, query, top_k=top_k)


def update_memory(memory_id: str, user_id: str, content: str | None = None,
                  importance: int | None = None) -> bool:
    return memory_repo.update(memory_id, user_id, content=content,
                              importance=importance)


def delete_memory(memory_id: str, user_id: str) -> bool:
    return memory_repo.soft_delete(memory_id, user_id)


def clear_memories(user_id: str) -> int:
    return memory_repo.clear_for_user(user_id)


def export_memories(user_id: str) -> list[dict[str, Any]]:
    return [m.to_dict() for m in memory_repo.list_for_user(user_id, limit=1000)]


def list_memories(user_id: str, memory_type: str = "") -> list[Memory]:
    return memory_repo.list_for_user(user_id, memory_type=memory_type)


def summarize_daily_memory(user_id: str, llm=None) -> Memory | None:
    """Compress today's episodic/emotional memories into one episodic summary."""
    recent = memory_repo.list_recent(user_id, days_ago_iso(1), limit=30)
    fragments = [m.content for m in recent if m.memory_type in ("episodic", "emotional")]
    if len(fragments) < 3:
        return None
    if llm is None:
        from app.services.llm_service import llm_service as llm
    try:
        summary = llm.summarize("；".join(fragments), max_tokens=80)
    except Exception as exc:  # noqa: BLE001
        log.warning("daily summary failed: %s", exc)
        return None
    return save_memory(user_id, "episodic", f"（当日总结）{summary}",
                       importance=3, confidence=0.9)
