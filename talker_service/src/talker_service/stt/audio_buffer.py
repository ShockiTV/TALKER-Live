"""Audio buffer for accumulating streamed audio chunks.

Collects base64-encoded audio chunks sent by ``talker_bridge`` as
``mic.audio.chunk`` messages, orders them by sequence number, and
yields the concatenated raw PCM bytes when finalized.

Supports both raw PCM and OGG/Vorbis compressed chunks — the bridge
sends OGG-compressed chunks by default to reduce wire payload size.
"""

from __future__ import annotations

import base64
import io
import threading
from typing import Optional

from loguru import logger

# soundfile is an optional dependency (part of [stt] extras)
try:
    import numpy as np
    import soundfile as sf
    _SF_AVAILABLE = True
except ImportError:
    _SF_AVAILABLE = False


class AudioBuffer:
    """Thread-safe buffer that accumulates ordered audio chunks.

    Usage::

        buf = AudioBuffer()
        buf.add_chunk(seq=1, audio_b64="...")
        buf.add_chunk(seq=2, audio_b64="...")
        pcm_bytes = buf.finalize()
    """

    def __init__(self) -> None:
        self._chunks: dict[int, bytes] = {}
        self._lock = threading.Lock()
        self._finalized = False

    @property
    def is_active(self) -> bool:
        """True if the buffer has been started and not yet finalized."""
        return not self._finalized

    @property
    def chunk_count(self) -> int:
        with self._lock:
            return len(self._chunks)

    def add_chunk(self, seq: int, audio_b64: str, fmt: str = "pcm") -> None:
        """Decode and store a single audio chunk.

        Args:
            seq: 1-based sequence number for ordering.
            audio_b64: Base64-encoded audio chunk (PCM or OGG/Vorbis).
            fmt: Audio format — ``"pcm"`` for raw int16 mono 16 kHz,
                 ``"ogg"`` for OGG/Vorbis compressed.

        Raises:
            ValueError: If the buffer has already been finalized.
        """
        if self._finalized:
            raise ValueError("Cannot add chunks to a finalized buffer")

        raw_b64 = base64.b64decode(audio_b64)

        if fmt == "ogg" and _SF_AVAILABLE:
            # Decompress OGG/Vorbis back to raw PCM int16
            data, _sr = sf.read(io.BytesIO(raw_b64), dtype="int16")
            pcm_bytes = data.tobytes()
        else:
            pcm_bytes = raw_b64

        with self._lock:
            self._chunks[seq] = pcm_bytes
        logger.debug("AudioBuffer: stored chunk seq={} ({} bytes, fmt={})",
                     seq, len(pcm_bytes), fmt)

    def finalize(self) -> bytes:
        """Concatenate chunks in order and return the full PCM byte stream.

        After calling this, no more chunks can be added.

        Returns:
            Concatenated raw PCM bytes (may be empty if no chunks received).
        """
        self._finalized = True
        with self._lock:
            if not self._chunks:
                logger.warning("AudioBuffer finalized with 0 chunks")
                return b""

            ordered = sorted(self._chunks.items())
            total = b"".join(data for _, data in ordered)
            count = len(self._chunks)
            self._chunks.clear()

        logger.info(
            "AudioBuffer finalized: {} chunks, {} bytes total",
            count,
            len(total),
        )
        return total

    def reset(self) -> None:
        """Discard all data and allow reuse."""
        with self._lock:
            self._chunks.clear()
        self._finalized = False
