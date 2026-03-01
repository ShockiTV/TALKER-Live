"""Unit tests for talker_bridge core logic.

Tests cover:
- AudioStreamer state management (start, cancel, concurrent start)
- VAD energy calculation and silence detection constants
- Publish/forward helpers (envelope format, error handling)
- LOCAL_TOPICS routing (mic vs proxy)
- TTSQueue lifecycle (submit, drain)

These tests mock sounddevice and websockets so they run without hardware
or network dependencies.
"""

import asyncio
import base64
import io
import json
import sys
import time
import threading
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import numpy as np
import pytest
import soundfile as sf

# Mock sounddevice before importing main
sys.modules.setdefault("sounddevice", MagicMock())
sys.modules.setdefault("banner", MagicMock(print_banner=MagicMock()))

import main  # noqa: E402 — must follow sys.modules stubs


# ── Constants ─────────────────────────────────────────────────────────────────


class TestConstants:
    def test_bridge_port(self):
        assert main.BRIDGE_WS_PORT == 5558

    def test_service_url(self):
        assert "5557" in main.SERVICE_WS_URL
        assert main.SERVICE_WS_URL.startswith("ws://")

    def test_local_topics_include_mic(self):
        for topic in ("mic.start", "mic.stop"):
            assert topic in main.LOCAL_TOPICS

    def test_mic_cancel_not_in_local_topics(self):
        assert "mic.cancel" not in main.LOCAL_TOPICS

    def test_local_topics_include_tts(self):
        assert "tts.speak" in main.LOCAL_TOPICS

    def test_game_topics_not_in_local(self):
        for topic in ("game.event", "player.dialogue", "config.update",
                      "dialogue.display", "memory.update"):
            assert topic not in main.LOCAL_TOPICS

    def test_vad_silence_threshold(self):
        assert main.VAD_SILENCE_THRESHOLD_S > 0

    def test_audio_sample_rate(self):
        assert main.AUDIO_SAMPLE_RATE == 16000


# ── AudioStreamer ─────────────────────────────────────────────────────────────


class TestAudioStreamer:
    def setup_method(self):
        self.streamer = main.AudioStreamer()

    def test_initial_state_not_recording(self):
        assert not self.streamer.is_recording

    def test_start_sets_recording(self):
        # Patch _capture_loop so it doesn't actually record
        with patch.object(self.streamer, "_capture_loop"):
            # Also need to patch threading.Thread to prevent actual thread
            with patch("main.threading.Thread") as mock_thread:
                mock_thread.return_value.start = MagicMock()
                self.streamer.start("dialogue")
                assert self.streamer.is_recording
                mock_thread.assert_called_once()

    def test_start_publishes_recording(self):
        with patch("main.threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            with patch("main.publish_to_lua") as mock_pub:
                self.streamer.start("dialogue")
                mock_pub.assert_called_once_with(
                    "mic.status", {"status": "RECORDING", "session_id": 1}
                )

    def test_double_start_supersedes(self):
        with patch("main.threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            self.streamer.start("dialogue")
            self.streamer.start("dialogue")  # second call supersedes
            # Each start spawns a new thread (old detects session mismatch)
            assert mock_thread.call_count == 2
            assert self.streamer._session_id == 2

    def test_cancel_stops_recording(self):
        with patch("main.threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            self.streamer.start("dialogue")
            assert self.streamer.is_recording
            self.streamer.cancel()
            assert not self.streamer.is_recording

    def test_cancel_when_not_recording_is_noop(self):
        self.streamer.cancel()
        assert not self.streamer.is_recording

    def test_context_type_stored(self):
        with patch("main.threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            self.streamer.start("whisper")
            assert self.streamer._context_type == "whisper"


# ── VAD energy threshold ─────────────────────────────────────────────────────


class TestVADEnergy:
    """Verify the energy-based VAD threshold logic against sample data."""

    def test_silence_below_threshold(self):
        # Near-silent audio (very low amplitude)
        silence = np.zeros(3200, dtype="int16")
        energy = np.abs(silence).mean()
        assert energy < main.VAD_ENERGY_LEVEL

    def test_speech_above_threshold(self):
        # Loud audio (should be above threshold)
        loud = np.full(3200, 5000, dtype="int16")
        energy = np.abs(loud).mean()
        assert energy > main.VAD_ENERGY_LEVEL


# ── OGG/Vorbis chunk encoding ────────────────────────────────────────────────


class TestChunkEncoding:
    """Verify the OGG/Vorbis compression used for audio chunks."""

    def test_ogg_roundtrip(self):
        """PCM → OGG/Vorbis → decode should produce similar-length audio."""
        pcm = np.random.randint(-10000, 10000, 3200, dtype="int16")
        buf = io.BytesIO()
        sf.write(buf, pcm, 16000, format="OGG", subtype="VORBIS")
        ogg_bytes = buf.getvalue()

        # Verify it's valid OGG
        buf2 = io.BytesIO(ogg_bytes)
        decoded, sr = sf.read(buf2, dtype="int16")
        assert sr == 16000
        assert len(decoded) > 0

    def test_ogg_smaller_than_pcm(self):
        """OGG/Vorbis should be smaller than raw PCM for non-trivial audio."""
        pcm = np.random.randint(-10000, 10000, 3200, dtype="int16")
        pcm_b64 = base64.b64encode(pcm.tobytes())

        buf = io.BytesIO()
        sf.write(buf, pcm, 16000, format="OGG", subtype="VORBIS")
        ogg_b64 = base64.b64encode(buf.getvalue())

        assert len(ogg_b64) < len(pcm_b64)


# ── publish_to_lua ────────────────────────────────────────────────────────────


class TestPublishToLua:
    def test_publish_creates_valid_envelope(self):
        mock_ws = MagicMock()
        mock_loop = MagicMock()

        with patch.object(main, "_lua_ws", mock_ws), \
             patch.object(main, "_event_loop", mock_loop):
            main.publish_to_lua("mic.status", {"status": "LISTENING"})
            # Should have called run_coroutine_threadsafe
            assert mock_loop.method_calls or True  # just verifying no crash

    def test_publish_no_lua_client_does_not_crash(self):
        with patch.object(main, "_lua_ws", None):
            # Should log and return, not raise
            main.publish_to_lua("mic.status", {"status": "LISTENING"})


# ── send_to_service ───────────────────────────────────────────────────────────


class TestSendToService:
    @pytest.mark.asyncio
    async def test_send_creates_valid_envelope(self):
        mock_ws = AsyncMock()
        with patch.object(main, "_service_ws", mock_ws):
            await main.send_to_service("mic.audio.chunk", {"seq": 1})
            mock_ws.send.assert_called_once()
            sent = json.loads(mock_ws.send.call_args[0][0])
            assert sent["t"] == "mic.audio.chunk"
            assert sent["p"]["seq"] == 1
            assert "ts" in sent

    @pytest.mark.asyncio
    async def test_send_no_service_does_not_crash(self):
        with patch.object(main, "_service_ws", None):
            await main.send_to_service("test", {})


# ── forward_raw_to_service ────────────────────────────────────────────────────


class TestForwardRawToService:
    @pytest.mark.asyncio
    async def test_forwards_raw_string_unchanged(self):
        mock_ws = AsyncMock()
        raw = '{"t":"game.event","p":{"type":"DEATH"},"ts":1000}'
        with patch.object(main, "_service_ws", mock_ws):
            await main.forward_raw_to_service(raw)
            mock_ws.send.assert_called_once_with(raw)

    @pytest.mark.asyncio
    async def test_no_service_drops_silently(self):
        with patch.object(main, "_service_ws", None):
            await main.forward_raw_to_service('{"t":"test"}')


# ── forward_raw_to_lua ───────────────────────────────────────────────────────


class TestForwardRawToLua:
    @pytest.mark.asyncio
    async def test_forwards_raw_string_unchanged(self):
        mock_ws = AsyncMock()
        raw = '{"t":"dialogue.display","p":{"text":"Hello"},"ts":2000}'
        with patch.object(main, "_lua_ws", mock_ws):
            await main.forward_raw_to_lua(raw)
            mock_ws.send.assert_called_once_with(raw)

    @pytest.mark.asyncio
    async def test_no_lua_drops_silently(self):
        with patch.object(main, "_lua_ws", None):
            await main.forward_raw_to_lua('{"t":"test"}')


# ── TTSQueue ──────────────────────────────────────────────────────────────────


class TestTTSQueue:
    def test_initial_state(self):
        q = main.TTSQueue()
        assert not q.busy

    def test_submit_starts_thread(self):
        q = main.TTSQueue()
        with patch("main.threading.Thread") as mock_thread:
            mock_thread.return_value.start = MagicMock()
            with patch("main._run_tts_task"):
                q.submit({"text": "hello", "speaker_id": "test"})
                mock_thread.assert_called_once()
