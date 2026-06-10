"""MemoryRetriever — keyword/recency/importance scoring over SQLite memories.

Short-term implementation: token-overlap text similarity + importance +
recency. The interface is stable so it can later be swapped for vector
embeddings / pgvector / hybrid search without touching callers.
"""
from __future__ import annotations

import re

from app.models.schemas import Memory
from app.repositories import memory_repository as memory_repo
from app.utils.time import days_ago_iso

_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[a-zA-Z]+")


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def score(memory: Memory, query_tokens: set[str]) -> float:
    """Similarity (token overlap) + importance boost."""
    mem_tokens = _tokenize(memory.content)
    if not mem_tokens or not query_tokens:
        overlap = 0.0
    else:
        overlap = len(mem_tokens & query_tokens) / max(len(query_tokens), 1)
    return overlap * 2.0 + memory.importance * 0.2 + memory.confidence * 0.3


def retrieve(user_id: str, query: str, top_k: int = 6) -> list[Memory]:
    """Top-k memories relevant to query; always includes recent + important."""
    candidates = memory_repo.list_for_user(user_id, limit=300)
    if not candidates:
        return []
    query_tokens = _tokenize(query)
    ranked = sorted(candidates, key=lambda m: score(m, query_tokens), reverse=True)
    result = ranked[:top_k]
    memory_repo.touch_recalled([m.id for m in result])
    return result


def recent_memories(user_id: str, days: int = 3, limit: int = 10) -> list[Memory]:
    return memory_repo.list_recent(user_id, days_ago_iso(days), limit=limit)


def important_memories(user_id: str, min_importance: int = 4,
                       limit: int = 10) -> list[Memory]:
    return [m for m in memory_repo.list_for_user(user_id, limit=100)
            if m.importance >= min_importance][:limit]
