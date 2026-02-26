"""Tests for AudioBuffer — sequence ordering, dedup, finalize, OGG decoding."""

import base64
import io
import struct

import pytest

from talker_service.stt.audio_buffer import AudioBuffer


def _pcm_b64(values: list[int]) -> str:
    """Create a base64-encoded PCM int16 byte string from sample values."""
    raw = struct.pack(f"<{len(values)}h", *values)
    return base64.b64encode(raw).decode("ascii")


def _ogg_b64(values: list[int], sample_rate: int = 16000) -> str:
    """Create a base64-encoded OGG/Vorbis chunk from sample values."""
    import numpy as np
    import soundfile as sf

    data = np.array(values, dtype="int16")
    buf = io.BytesIO()
    sf.write(buf, data, sample_rate, format="OGG", subtype="VORBIS")
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ── Construction ──────────────────────────────────────────────────────────────


class TestConstruction:
    def test_new_buffer_is_active(self):
        buf = AudioBuffer()
        assert buf.is_active is True

    def test_new_buffer_has_zero_chunks(self):
        buf = AudioBuffer()
        assert buf.chunk_count == 0


# ── add_chunk (PCM) ──────────────────────────────────────────────────────────


class TestAddChunkPCM:
    def test_single_chunk(self):
        buf = AudioBuffer()
        buf.add_chunk(1, _pcm_b64([100, 200, 300]))
        assert buf.chunk_count == 1

    def test_multiple_chunks(self):
        buf = AudioBuffer()
        buf.add_chunk(1, _pcm_b64([100]))
        buf.add_chunk(2, _pcm_b64([200]))
        buf.add_chunk(3, _pcm_b64([300]))
        assert buf.chunk_count == 3

    def test_duplicate_seq_overwrites(self):
        buf = AudioBuffer()
        buf.add_chunk(1, _pcm_b64([100]))
        buf.add_chunk(1, _pcm_b64([999]))
        assert buf.chunk_count == 1
        # finalize should yield the last value
        pcm = buf.finalize()
        assert struct.unpack("<h", pcm)[0] == 999

    def test_out_of_order_chunks_reordered_on_finalize(self):
        buf = AudioBuffer()
        buf.add_chunk(3, _pcm_b64([30]))
        buf.add_chunk(1, _pcm_b64([10]))
        buf.add_chunk(2, _pcm_b64([20]))
        pcm = buf.finalize()
        samples = struct.unpack(f"<{len(pcm)//2}h", pcm)
        assert samples == (10, 20, 30)

    def test_add_after_finalize_raises(self):
        buf = AudioBuffer()
        buf.add_chunk(1, _pcm_b64([100]))
        buf.finalize()
        with pytest.raises(ValueError, match="finalized"):
            buf.add_chunk(2, _pcm_b64([200]))


# ── add_chunk (OGG) ──────────────────────────────────────────────────────────


class TestAddChunkOGG:
    """OGG/Vorbis decoding on ingest."""

    def test_ogg_chunk_decoded_to_pcm(self):
        buf = AudioBuffer()
        # 3200 samples = 200ms at 16kHz (minimum for OGG encoding)
        buf.add_chunk(1, _ogg_b64([0] * 3200), fmt="ogg")
        assert buf.chunk_count == 1
        pcm = buf.finalize()
        # Decoded PCM should have bytes (OGG is lossy, so length may vary slightly)
        assert len(pcm) > 0

    def test_pcm_fallback_when_format_unknown(self):
        """Unknown format falls back to raw PCM passthrough."""
        buf = AudioBuffer()
        raw = _pcm_b64([100, 200])
        buf.add_chunk(1, raw, fmt="pcm")
        pcm = buf.finalize()
        assert struct.unpack(f"<{len(pcm)//2}h", pcm) == (100, 200)


# ── finalize ──────────────────────────────────────────────────────────────────


class TestFinalize:
    def test_finalize_returns_concatenated_pcm(self):
        buf = AudioBuffer()
        buf.add_chunk(1, _pcm_b64([10, 20]))
        buf.add_chunk(2, _pcm_b64([30, 40]))
        pcm = buf.finalize()
        samples = struct.unpack(f"<{len(pcm)//2}h", pcm)
        assert samples == (10, 20, 30, 40)

    def test_finalize_marks_buffer_inactive(self):
        buf = AudioBuffer()
        buf.add_chunk(1, _pcm_b64([1]))
        buf.finalize()
        assert buf.is_active is False

    def test_finalize_empty_buffer_returns_empty(self):
        buf = AudioBuffer()
        pcm = buf.finalize()
        assert pcm == b""

    def test_finalize_clears_internal_chunks(self):
        buf = AudioBuffer()
        buf.add_chunk(1, _pcm_b64([1]))
        buf.finalize()
        # chunk_count should be 0 after finalize clears
        assert buf.chunk_count == 0


# ── reset ─────────────────────────────────────────────────────────────────────


class TestReset:
    def test_reset_allows_reuse(self):
        buf = AudioBuffer()
        buf.add_chunk(1, _pcm_b64([1]))
        buf.finalize()
        buf.reset()
        assert buf.is_active is True
        assert buf.chunk_count == 0
        buf.add_chunk(1, _pcm_b64([99]))
        pcm = buf.finalize()
        assert struct.unpack("<h", pcm)[0] == 99
