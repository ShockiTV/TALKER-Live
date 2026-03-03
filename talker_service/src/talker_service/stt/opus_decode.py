"""Opus frame decoder for native mic capture audio.

Decodes individual Opus frames to 16-bit PCM (16 kHz mono) using PyAV (ffmpeg).
Falls back gracefully when PyAV is not installed — callers check
``OPUS_AVAILABLE`` before using.
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger

try:
    import av  # type: ignore[import-untyped]

    OPUS_AVAILABLE = True
except (ImportError, OSError):
    OPUS_AVAILABLE = False
    logger.debug("PyAV (av) not available — Opus decode disabled")


_TARGET_RATE = 16000
_CHANNELS = 1


def create_decoder() -> Optional[Any]:
    """Create and return a new Opus codec context via PyAV.

    Returns:
        An ``av.CodecContext`` configured for Opus decoding, or ``None``
        if PyAV is unavailable.
    """
    if not OPUS_AVAILABLE:
        return None
    try:
        ctx = av.CodecContext.create("libopus", "r")
        ctx.sample_rate = 48000  # Opus native decode rate
        ctx.layout = "mono"
        ctx.open()
        return ctx
    except Exception:
        logger.opt(exception=True).error("Failed to create Opus decoder (PyAV)")
        return None


def decode_frames(decoder: Any, opus_frames: list[bytes],
                  frame_ms: int = 20) -> bytes:
    """Decode a list of Opus frames to concatenated PCM int16 bytes.

    Uses PyAV's ``CodecContext`` to decode each raw Opus packet, then
    resamples from 48 kHz (Opus native) to 16 kHz mono int16.

    Args:
        decoder: An ``av.CodecContext`` from :func:`create_decoder`.
        opus_frames: List of raw Opus-encoded frame bytes.
        frame_ms: Duration of each frame in ms (default 20).

    Returns:
        Concatenated raw PCM bytes (int16 LE, 16 kHz, mono).
        Frames that fail to decode are silently skipped.
    """
    resampler = av.AudioResampler(format="s16", layout="mono", rate=_TARGET_RATE)
    pcm_parts: list[bytes] = []

    for i, frame_data in enumerate(opus_frames):
        try:
            packet = av.Packet(frame_data)
            for audio_frame in decoder.decode(packet):
                for resampled in resampler.resample(audio_frame):
                    pcm_parts.append(resampled.to_ndarray().tobytes())
        except Exception:
            logger.warning("Opus decode failed for frame {} ({} bytes) — skipping",
                           i, len(frame_data))

    # Flush the decoder and resampler
    try:
        for audio_frame in decoder.decode(None):
            for resampled in resampler.resample(audio_frame):
                pcm_parts.append(resampled.to_ndarray().tobytes())
        for resampled in resampler.resample(None):
            pcm_parts.append(resampled.to_ndarray().tobytes())
    except Exception:
        pass

    return b"".join(pcm_parts)
