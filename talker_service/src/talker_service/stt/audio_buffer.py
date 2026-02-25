"""Audio buffer for accumulating streamed audio chunks.

Collects base64-encoded audio chunks sent by ``talker_bridge`` as
``mic.audio.chunk`` messages, orders them by sequence number, and
yields the concatenated raw PCM bytes when finalized.
"""

from __future__ import annotations

import base64
import threading
from typing import Optional

from loguru import logger


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

    def add_chunk(self, seq: int, audio_b64: str) -> None:
        """Decode and store a single audio chunk.

        Args:
            seq: 1-based sequence number for ordering.
            audio_b64: Base64-encoded raw PCM int16 mono audio.

        Raises:
            ValueError: If the buffer has already been finalized.
        """
        if self._finalized:
            raise ValueError("Cannot add chunks to a finalized buffer")

        raw = base64.b64decode(audio_b64)
        with self._lock:
            self._chunks[seq] = raw
        logger.debug("AudioBuffer: stored chunk seq={} ({} bytes)", seq, len(raw))

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
