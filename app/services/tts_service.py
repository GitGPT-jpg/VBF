"""TTSService — unified text-to-speech with audio asset bookkeeping.

Wraps the legacy `tts_module` pipeline (edge-tts → optional RVC) and records
every generated clip as an `audio_assets` row with a serveable URL.

Reserved interfaces for future realtime voice are declared at the bottom:
streaming_tts / streaming_asr / interrupt_audio / voice_activity_detection.
"""
from __future__ import annotations

import os
from typing import Iterator

from app.models.schemas import AudioAsset
from app.repositories import audio_repository as audio_repo
from app.utils.logger import get_logger

log = get_logger(__name__)


def synthesize(text: str, user_id: str, message_id: str = "",
               slow: bool = False) -> AudioAsset | None:
    """Generate speech for text; returns the persisted AudioAsset or None."""
    if not text.strip():
        return None
    try:
        from tts_module import tts as legacy_tts  # lazy: heavy deps
        path = legacy_tts(text, slow=slow)
    except Exception as exc:  # noqa: BLE001
        log.warning("TTS failed: %s", exc)
        return None
    if not path or not os.path.exists(path):
        return None
    provider = "edge+rvc" if path.endswith("_rvc.wav") else "edge"
    asset = audio_repo.create(
        user_id=user_id, asset_type="tts", file_path=path,
        public_url=f"/audio/tts/{os.path.basename(path)}",
        message_id=message_id, provider=provider)
    return asset


def register_song_asset(user_id: str, file_path: str, message_id: str = "",
                        title: str = "") -> AudioAsset | None:
    """Record a finished song render as an audio asset."""
    if not file_path or not os.path.exists(file_path):
        return None
    return audio_repo.create(
        user_id=user_id, asset_type="song", file_path=file_path,
        public_url=f"/audio/sing/{os.path.basename(file_path)}",
        message_id=message_id, provider="replicate-rvc",
        metadata={"title": title})


# ── Reserved realtime-voice interfaces (mid-term roadmap) ────────────────────

def streaming_tts(text_stream: Iterator[str], user_id: str) -> Iterator[bytes]:
    """Stream audio chunks for a token stream. Not yet implemented."""
    raise NotImplementedError("streaming TTS is on the roadmap")


def streaming_asr(audio_stream: Iterator[bytes]) -> Iterator[str]:
    """Stream transcription for an audio stream. Not yet implemented."""
    raise NotImplementedError("streaming ASR is on the roadmap")


def interrupt_audio(user_id: str) -> None:
    """Cancel in-flight synthesis for a user. No-op until streaming lands."""
    log.debug("interrupt_audio called for %s (no-op)", user_id)


def voice_activity_detection(audio_chunk: bytes) -> bool:
    """VAD hook for call mode. Not yet implemented."""
    raise NotImplementedError("VAD is on the roadmap")
