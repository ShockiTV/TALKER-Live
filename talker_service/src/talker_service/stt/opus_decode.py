"""Opus frame decoder for native mic capture audio.

Decodes individual Opus frames to 16-bit PCM (16 kHz mono) using opuslib.
Falls back gracefully when opuslib is not installed — callers check
``OPUS_AVAILABLE`` before using.
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

try:
    import opuslib  # type: ignore[import-untyped]

    OPUS_AVAILABLE = True
except (ImportError, OSError):
    OPUS_AVAILABLE = False
    logger.debug("opuslib not available — Opus decode disabled")


# Opus frame size for 20ms at 16 kHz mono = 320 samples
_SAMPLE_RATE = 16000
_CHANNELS = 1
_FRAME_SIZE_20MS = 320  # 20ms * 16000 / 1000


def create_decoder() -> Optional["opuslib.Decoder"]:
    """Create and return a new Opus decoder for 16 kHz mono.

    Returns:
        An ``opuslib.Decoder`` instance, or ``None`` if opuslib is unavailable.
    """
    if not OPUS_AVAILABLE:
        return None
    try:
        return opuslib.Decoder(_SAMPLE_RATE, _CHANNELS)
    except Exception:
        logger.opt(exception=True).error("Failed to create Opus decoder")
        return None


def decode_frames(decoder: "opuslib.Decoder", opus_frames: list[bytes],
                  frame_ms: int = 20) -> bytes:
    """Decode a list of Opus frames to concatenated PCM int16 bytes.

    Args:
        decoder: An ``opuslib.Decoder`` instance.
        opus_frames: List of raw Opus-encoded frame bytes.
        frame_ms: Duration of each frame in ms (default 20).

    Returns:
        Concatenated raw PCM bytes (int16 LE, 16 kHz, mono).
        Frames that fail to decode are silently skipped.
    """
    frame_size = (_SAMPLE_RATE * frame_ms) // 1000
    pcm_parts: list[bytes] = []

    for i, frame_data in enumerate(opus_frames):
        try:
            pcm = decoder.decode(frame_data, frame_size)
            pcm_parts.append(pcm)
        except Exception:
            logger.warning("Opus decode failed for frame {} ({} bytes) — skipping",
                           i, len(frame_data))

    return b"".join(pcm_parts)
