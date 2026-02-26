"""Handlers for microphone audio topics received from talker_bridge.

Manages the audio buffer lifecycle:
1. ``mic.audio.chunk`` — buffer incoming PCM chunks in order
2. ``mic.audio.end``   — finalize buffer, run STT, send result, trigger dialogue

These handlers are registered in ``__main__.py`` only when STT is available.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional, TYPE_CHECKING

from loguru import logger

from ..stt.audio_buffer import AudioBuffer

if TYPE_CHECKING:
    from ..stt.base import STTProvider
    from ..handlers.events import PublisherProtocol

# Injected by __main__.py
_stt_provider: Optional["STTProvider"] = None
_publisher: Optional["PublisherProtocol"] = None

# Active audio buffer (one session at a time)
_audio_buffer: Optional[AudioBuffer] = None
_buffer_lock = asyncio.Lock()


def set_stt_provider(provider: "STTProvider") -> None:
    """Inject the STT provider instance."""
    global _stt_provider
    _stt_provider = provider
    logger.info("STT provider injected into audio handlers")


def set_audio_publisher(publisher: "PublisherProtocol") -> None:
    """Inject the publisher for sending results back to Lua via bridge."""
    global _publisher
    _publisher = publisher
    logger.info("Publisher injected into audio handlers")


async def handle_audio_chunk(payload: dict[str, Any]) -> None:
    """Handle ``mic.audio.chunk`` — buffer a single audio chunk.

    Payload::

        {"audio_b64": "<base64>", "seq": <int>}
    """
    global _audio_buffer

    seq = payload.get("seq", 0)
    audio_b64 = payload.get("audio_b64", "")

    if not audio_b64:
        logger.warning("mic.audio.chunk: empty audio_b64 (seq={})", seq)
        return

    async with _buffer_lock:
        if _audio_buffer is None:
            # First chunk starts a new buffer implicitly
            _audio_buffer = AudioBuffer()
            logger.info("AudioBuffer created on first chunk")

        fmt = payload.get("format", "pcm")
        try:
            _audio_buffer.add_chunk(seq, audio_b64, fmt=fmt)
        except ValueError:
            # Buffer was already finalized — start a fresh one
            _audio_buffer = AudioBuffer()
            _audio_buffer.add_chunk(seq, audio_b64, fmt=fmt)
            logger.info("AudioBuffer reset on stale chunk (seq={})", seq)


async def handle_audio_end(payload: dict[str, Any]) -> None:
    """Handle ``mic.audio.end`` — finalize buffer and run transcription.

    Payload::

        {"context": {"type": "dialogue" | "whisper"}}

    After transcription, sends:
    - ``mic.status`` with ``{"status": "TRANSCRIBING"}``
    - ``mic.result`` with ``{"text": "..."}``

    Then triggers dialogue generation via ``player.dialogue`` or ``player.whisper``.
    """
    global _audio_buffer

    context = payload.get("context", {})
    context_type = context.get("type", "dialogue") if isinstance(context, dict) else "dialogue"

    async with _buffer_lock:
        buf = _audio_buffer
        _audio_buffer = None  # Allow new session immediately

    if buf is None or buf.chunk_count == 0:
        logger.warning("mic.audio.end received but no audio buffered")
        return

    # Notify Lua that transcription is starting
    if _publisher:
        await _publisher.publish("mic.status", {"status": "TRANSCRIBING"})

    # Run transcription in a thread to avoid blocking the event loop
    pcm_bytes = buf.finalize()
    text = await _run_transcription(pcm_bytes)

    if not text:
        logger.warning("Transcription returned empty text")
        if _publisher:
            await _publisher.publish("mic.result", {"text": ""})
        return

    # Send result back to Lua (bridge proxies it downstream)
    if _publisher:
        await _publisher.publish("mic.result", {"text": text})
    logger.info("Transcription result sent: '{}' (context={})", text, context_type)

    # Trigger dialogue generation using the standard handler path
    from .events import handle_player_dialogue, handle_player_whisper

    dialogue_payload = {"text": text, "context": context}
    if context_type == "whisper":
        asyncio.create_task(handle_player_whisper(dialogue_payload))
    else:
        asyncio.create_task(handle_player_dialogue(dialogue_payload))


async def _run_transcription(pcm_bytes: bytes) -> str:
    """Run the STT provider in a thread pool executor."""
    if _stt_provider is None:
        logger.error("No STT provider available — cannot transcribe")
        return ""

    loop = asyncio.get_event_loop()
    try:
        text = await loop.run_in_executor(
            None,
            lambda: _stt_provider.transcribe(pcm_bytes),
        )
        return text or ""
    except Exception:
        logger.opt(exception=True).error("Transcription failed")
        return ""
