"""Audio buffer for accumulating streamed audio chunks.

Collects base64-encoded audio chunks sent by ``talker_bridge`` (or Lua directly)
as ``mic.audio.chunk`` messages, orders them by sequence number, and yields the
concatenated raw PCM bytes when finalized.

Supports three audio formats:
- ``pcm``  — raw int16 mono 16 kHz (stored directly)
- ``ogg``  — OGG/Vorbis compressed (decoded on add via soundfile)
- ``opus`` — individual Opus frames (stored raw, decoded to PCM on finalize)
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

# Opus decode support (optional, part of [stt] extras)
from .opus_decode import OPUS_AVAILABLE, create_decoder, decode_frames


class AudioBuffer:
    """Thread-safe buffer that accumulates ordered audio chunks.

    Usage::

        buf = AudioBuffer()
        buf.add_chunk(seq=1, audio_b64="...", fmt="opus")
        buf.add_chunk(seq=2, audio_b64="...", fmt="opus")
        pcm_bytes = buf.finalize()
    """

    def __init__(self) -> None:
        self._chunks: dict[int, bytes] = {}       # seq → PCM bytes (pcm/ogg)
        self._opus_chunks: dict[int, bytes] = {}   # seq → raw Opus frames
        self._lock = threading.Lock()
        self._finalized = False
        self._has_opus = False

    @property
    def is_active(self) -> bool:
        """True if the buffer has been started and not yet finalized."""
        return not self._finalized

    @property
    def chunk_count(self) -> int:
        with self._lock:
            return len(self._chunks) + len(self._opus_chunks)

    def add_chunk(self, seq: int, audio_b64: str, fmt: str = "pcm") -> None:
        """Decode and store a single audio chunk.

        Args:
            seq: 1-based sequence number for ordering.
            audio_b64: Base64-encoded audio chunk.
            fmt: Audio format — ``"pcm"`` for raw int16 mono 16 kHz,
                 ``"ogg"`` for OGG/Vorbis compressed,
                 ``"opus"`` for individual Opus frames.

        Raises:
            ValueError: If the buffer has already been finalized.
        """
        if self._finalized:
            raise ValueError("Cannot add chunks to a finalized buffer")

        raw_bytes = base64.b64decode(audio_b64)

        if fmt == "opus":
            # Store raw Opus frame — decode in bulk on finalize()
            with self._lock:
                self._opus_chunks[seq] = raw_bytes
                self._has_opus = True
            logger.debug("AudioBuffer: stored opus chunk seq={} ({} bytes)",
                         seq, len(raw_bytes))
            return

        if fmt == "ogg" and _SF_AVAILABLE:
            # Decompress OGG/Vorbis back to raw PCM int16
            data, _sr = sf.read(io.BytesIO(raw_bytes), dtype="int16")
            pcm_bytes = data.tobytes()
        else:
            pcm_bytes = raw_bytes

        with self._lock:
            self._chunks[seq] = pcm_bytes
        logger.debug("AudioBuffer: stored chunk seq={} ({} bytes, fmt={})",
                     seq, len(pcm_bytes), fmt)

    def finalize(self) -> bytes:
        """Concatenate chunks in order and return the full PCM byte stream.

        For Opus chunks, decodes all frames to PCM before concatenation.
        After calling this, no more chunks can be added.

        Returns:
            Concatenated raw PCM bytes (may be empty if no chunks received).
        """
        self._finalized = True
        with self._lock:
            has_pcm = bool(self._chunks)
            has_opus = bool(self._opus_chunks)

            if not has_pcm and not has_opus:
                logger.warning("AudioBuffer finalized with 0 chunks")
                return b""

            pcm_parts: list[bytes] = []

            # Decode Opus frames if present
            if has_opus:
                ordered_opus = [data for _, data in sorted(self._opus_chunks.items())]
                self._opus_chunks.clear()

                if OPUS_AVAILABLE:
                    decoder = create_decoder()
                    if decoder is not None:
                        pcm_from_opus = decode_frames(decoder, ordered_opus)
                        pcm_parts.append(pcm_from_opus)
                        logger.info("AudioBuffer: decoded {} Opus frames → {} PCM bytes",
                                    len(ordered_opus), len(pcm_from_opus))
                    else:
                        logger.error("AudioBuffer: Opus decoder creation failed — "
                                     "{} frames discarded", len(ordered_opus))
                else:
                    logger.error("AudioBuffer: opuslib not available — "
                                 "{} Opus frames discarded", len(ordered_opus))

            # Append PCM/OGG chunks (already decoded)
            if has_pcm:
                ordered_pcm = sorted(self._chunks.items())
                pcm_parts.extend(data for _, data in ordered_pcm)
                self._chunks.clear()

            total = b"".join(pcm_parts)
            count = (len(ordered_opus) if has_opus else 0) + (len(ordered_pcm) if has_pcm else 0)

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
            self._opus_chunks.clear()
        self._finalized = False
        self._has_opus = False
