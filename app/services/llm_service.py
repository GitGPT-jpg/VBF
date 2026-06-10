"""LLMService — single Anthropic client wrapper used by all layers.

Provides:
- complete(): one-shot completion
- stream(): token generator for streaming replies
- classify_json(): cheap classification call returning raw text
Reserved for future realtime voice: streaming_tts/streaming_asr hooks live in
tts_service; this module stays text-only.
"""
from __future__ import annotations

import threading
from typing import Iterator

from app.config.settings import settings
from app.utils.logger import get_logger

log = get_logger(__name__)


class LLMService:
    def __init__(self, model: str | None = None) -> None:
        self.model = model or settings.anthropic_model
        self._client = None
        self._lock = threading.Lock()

    def _get_client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    import anthropic  # lazy: keeps tests import-light
                    self._client = anthropic.Anthropic(
                        api_key=settings.anthropic_api_key,
                        base_url=settings.anthropic_base_url,
                    )
        return self._client

    def complete(self, system: str, messages: list[dict[str, str]],
                 max_tokens: int = 200) -> str:
        response = self._get_client().messages.create(
            model=self.model, max_tokens=max_tokens,
            system=system, messages=messages)
        return response.content[0].text.strip()

    def stream(self, system: str, messages: list[dict[str, str]],
               max_tokens: int = 200) -> Iterator[str]:
        """Yield text chunks. Raises on API errors — callers handle fallback."""
        with self._get_client().messages.stream(
                model=self.model, max_tokens=max_tokens,
                system=system, messages=messages) as stream:
            yield from stream.text_stream

    def classify_json(self, system: str, user: str, max_tokens: int = 150) -> str:
        """Lightweight classification call; returns raw model text (JSON expected)."""
        return self.complete(system, [{"role": "user", "content": user}],
                             max_tokens=max_tokens)

    def summarize(self, text: str, max_tokens: int = 60) -> str:
        try:
            return self.complete(
                "你是一个对话摘要器。只输出一句话摘要。",
                [{"role": "user", "content": f"压缩为一句话：\n{text}"}],
                max_tokens=max_tokens)
        except Exception as exc:  # noqa: BLE001
            log.warning("summarize failed: %s", exc)
            return "（之前聊过一会儿了）"


llm_service = LLMService()
