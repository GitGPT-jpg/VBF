"""LLMService — provider-agnostic LLM wrapper used by all layers.

Supported providers (via LLM_PROVIDER env var):
    anthropic            — Claude (default)
    openai | deepseek    — any OpenAI-compatible chat-completions endpoint

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

_OPENAI_COMPATIBLE = {"openai", "deepseek"}


class LLMService:
    def __init__(self, provider: str | None = None, model: str | None = None) -> None:
        self.provider = (provider or settings.llm_provider or "anthropic").lower()
        if self.provider in _OPENAI_COMPATIBLE:
            self.model = model or settings.openai_model
        else:
            self.model = model or settings.anthropic_model
        self._client = None
        self._lock = threading.Lock()

    # ── client bootstrap ─────────────────────────────────────────────────────
    def _get_client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    self._client = self._build_client()
        return self._client

    def _build_client(self):
        if self.provider in _OPENAI_COMPATIBLE:
            from openai import OpenAI  # lazy import
            return OpenAI(api_key=settings.openai_api_key,
                          base_url=settings.openai_base_url)
        import anthropic  # lazy import
        return anthropic.Anthropic(api_key=settings.anthropic_api_key,
                                   base_url=settings.anthropic_base_url)

    # ── completions ──────────────────────────────────────────────────────────
    def complete(self, system: str, messages: list[dict[str, str]],
                 max_tokens: int = 200) -> str:
        if self.provider in _OPENAI_COMPATIBLE:
            resp = self._get_client().chat.completions.create(
                model=self.model, max_tokens=max_tokens,
                messages=[{"role": "system", "content": system}, *messages])
            return (resp.choices[0].message.content or "").strip()
        resp = self._get_client().messages.create(
            model=self.model, max_tokens=max_tokens,
            system=system, messages=messages)
        return resp.content[0].text.strip()

    def stream(self, system: str, messages: list[dict[str, str]],
               max_tokens: int = 200) -> Iterator[str]:
        """Yield text chunks. Raises on API errors — callers handle fallback."""
        if self.provider in _OPENAI_COMPATIBLE:
            stream = self._get_client().chat.completions.create(
                model=self.model, max_tokens=max_tokens, stream=True,
                messages=[{"role": "system", "content": system}, *messages])
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
            return
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
