"""Tests for audio handlers — chunk buffering, end-of-stream, transcription."""

import asyncio
import base64
import struct

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.handlers import audio as audio_mod
from talker_service.stt.audio_buffer import AudioBuffer


def _pcm_b64(values: list[int]) -> str:
    raw = struct.pack(f"<{len(values)}h", *values)
    return base64.b64encode(raw).decode("ascii")


@pytest.fixture(autouse=True)
def _reset_audio_module():
    """Reset module-level state before each test."""
    audio_mod._audio_buffer = None
    audio_mod._stt_provider = None
    audio_mod._publisher = None
    yield
    audio_mod._audio_buffer = None
    audio_mod._stt_provider = None
    audio_mod._publisher = None


# ── set_stt_provider / set_audio_publisher ────────────────────────────────────


class TestInjection:
    def test_set_stt_provider(self):
        mock = MagicMock()
        audio_mod.set_stt_provider(mock)
        assert audio_mod._stt_provider is mock

    def test_set_audio_publisher(self):
        mock = AsyncMock()
        audio_mod.set_audio_publisher(mock)
        assert audio_mod._publisher is mock


# ── handle_audio_chunk ────────────────────────────────────────────────────────


class TestHandleAudioChunk:
    @pytest.mark.asyncio
    async def test_creates_buffer_on_first_chunk(self):
        await audio_mod.handle_audio_chunk({
            "audio_b64": _pcm_b64([100]),
            "seq": 1,
        })
        assert audio_mod._audio_buffer is not None
        assert audio_mod._audio_buffer.chunk_count == 1

    @pytest.mark.asyncio
    async def test_accumulates_multiple_chunks(self):
        for i in range(1, 4):
            await audio_mod.handle_audio_chunk({
                "audio_b64": _pcm_b64([i * 100]),
                "seq": i,
            })
        assert audio_mod._audio_buffer.chunk_count == 3

    @pytest.mark.asyncio
    async def test_empty_audio_b64_ignored(self):
        await audio_mod.handle_audio_chunk({"audio_b64": "", "seq": 1})
        assert audio_mod._audio_buffer is None

    @pytest.mark.asyncio
    async def test_resets_on_finalized_buffer(self):
        # Create and finalize a buffer
        await audio_mod.handle_audio_chunk({
            "audio_b64": _pcm_b64([100]),
            "seq": 1,
        })
        audio_mod._audio_buffer.finalize()

        # Next chunk should start a fresh buffer
        await audio_mod.handle_audio_chunk({
            "audio_b64": _pcm_b64([200]),
            "seq": 1,
        })
        assert audio_mod._audio_buffer.chunk_count == 1

    @pytest.mark.asyncio
    async def test_format_field_passed_through(self):
        """The 'format' field is forwarded to AudioBuffer.add_chunk."""
        with patch.object(AudioBuffer, "add_chunk") as mock_add:
            await audio_mod.handle_audio_chunk({
                "audio_b64": _pcm_b64([100]),
                "seq": 1,
                "format": "ogg",
            })
            mock_add.assert_called_once_with(1, _pcm_b64([100]), fmt="ogg")


# ── handle_audio_end ──────────────────────────────────────────────────────────


class TestHandleAudioEnd:
    @pytest.mark.asyncio
    async def test_no_buffer_sends_nothing(self):
        publisher = AsyncMock()
        audio_mod.set_audio_publisher(publisher)
        await audio_mod.handle_audio_end({"context": {"type": "dialogue"}})
        # Should not crash; no mic.result or mic.status published
        publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_buffer_sends_nothing(self):
        publisher = AsyncMock()
        audio_mod.set_audio_publisher(publisher)
        audio_mod._audio_buffer = AudioBuffer()  # 0 chunks
        await audio_mod.handle_audio_end({"context": {"type": "dialogue"}})
        publisher.publish.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_transcribing_status(self):
        publisher = AsyncMock()
        provider = MagicMock()
        provider.transcribe.return_value = "hello"
        audio_mod.set_audio_publisher(publisher)
        audio_mod.set_stt_provider(provider)

        # Buffer a chunk
        await audio_mod.handle_audio_chunk({
            "audio_b64": _pcm_b64([100, 200, 300]),
            "seq": 1,
        })

        with patch("talker_service.handlers.events.handle_player_dialogue",
                    new_callable=AsyncMock):
            await audio_mod.handle_audio_end({"context": {"type": "dialogue"}})

        # Should have sent TRANSCRIBING status
        calls = publisher.publish.call_args_list
        assert any(
            c.args[0] == "mic.status" and c.args[1].get("status") == "TRANSCRIBING"
            for c in calls
        )

    @pytest.mark.asyncio
    async def test_sends_mic_result(self):
        publisher = AsyncMock()
        provider = MagicMock()
        provider.transcribe.return_value = "hello stalker"
        audio_mod.set_audio_publisher(publisher)
        audio_mod.set_stt_provider(provider)

        await audio_mod.handle_audio_chunk({
            "audio_b64": _pcm_b64([100]),
            "seq": 1,
        })

        with patch("talker_service.handlers.events.handle_player_dialogue",
                    new_callable=AsyncMock):
            await audio_mod.handle_audio_end({"context": {"type": "dialogue"}})

        calls = publisher.publish.call_args_list
        assert any(
            c.args[0] == "mic.result" and c.args[1].get("text") == "hello stalker"
            for c in calls
        )

    @pytest.mark.asyncio
    async def test_empty_transcription_sends_empty_result(self):
        publisher = AsyncMock()
        provider = MagicMock()
        provider.transcribe.return_value = ""
        audio_mod.set_audio_publisher(publisher)
        audio_mod.set_stt_provider(provider)

        await audio_mod.handle_audio_chunk({
            "audio_b64": _pcm_b64([100]),
            "seq": 1,
        })

        await audio_mod.handle_audio_end({"context": {"type": "dialogue"}})

        calls = publisher.publish.call_args_list
        assert any(
            c.args[0] == "mic.result" and c.args[1].get("text") == ""
            for c in calls
        )

    @pytest.mark.asyncio
    async def test_triggers_dialogue_on_context_dialogue(self):
        publisher = AsyncMock()
        provider = MagicMock()
        provider.transcribe.return_value = "test text"
        audio_mod.set_audio_publisher(publisher)
        audio_mod.set_stt_provider(provider)

        await audio_mod.handle_audio_chunk({
            "audio_b64": _pcm_b64([100]),
            "seq": 1,
        })

        with patch("talker_service.handlers.events.handle_player_dialogue",
                    new_callable=AsyncMock) as mock_dialogue:
            await audio_mod.handle_audio_end({"context": {"type": "dialogue"}})
            # Let the task run
            await asyncio.sleep(0.05)
            mock_dialogue.assert_called_once()

    @pytest.mark.asyncio
    async def test_triggers_whisper_on_context_whisper(self):
        publisher = AsyncMock()
        provider = MagicMock()
        provider.transcribe.return_value = "whisper text"
        audio_mod.set_audio_publisher(publisher)
        audio_mod.set_stt_provider(provider)

        await audio_mod.handle_audio_chunk({
            "audio_b64": _pcm_b64([100]),
            "seq": 1,
        })

        with patch("talker_service.handlers.events.handle_player_whisper",
                    new_callable=AsyncMock) as mock_whisper:
            await audio_mod.handle_audio_end({"context": {"type": "whisper"}})
            await asyncio.sleep(0.05)
            mock_whisper.assert_called_once()

    @pytest.mark.asyncio
    async def test_clears_buffer_after_processing(self):
        publisher = AsyncMock()
        provider = MagicMock()
        provider.transcribe.return_value = "text"
        audio_mod.set_audio_publisher(publisher)
        audio_mod.set_stt_provider(provider)

        await audio_mod.handle_audio_chunk({
            "audio_b64": _pcm_b64([100]),
            "seq": 1,
        })

        with patch("talker_service.handlers.events.handle_player_dialogue",
                    new_callable=AsyncMock):
            await audio_mod.handle_audio_end({"context": {"type": "dialogue"}})

        assert audio_mod._audio_buffer is None

    @pytest.mark.asyncio
    async def test_default_context_type_is_dialogue(self):
        """Missing context or type defaults to 'dialogue'."""
        publisher = AsyncMock()
        provider = MagicMock()
        provider.transcribe.return_value = "test"
        audio_mod.set_audio_publisher(publisher)
        audio_mod.set_stt_provider(provider)

        await audio_mod.handle_audio_chunk({
            "audio_b64": _pcm_b64([100]),
            "seq": 1,
        })

        with patch("talker_service.handlers.events.handle_player_dialogue",
                    new_callable=AsyncMock) as mock_d:
            await audio_mod.handle_audio_end({})  # No context
            await asyncio.sleep(0.05)
            mock_d.assert_called_once()


# ── _run_transcription ────────────────────────────────────────────────────────


class TestRunTranscription:
    @pytest.mark.asyncio
    async def test_no_provider_returns_empty(self):
        audio_mod._stt_provider = None
        result = await audio_mod._run_transcription(b"\x00\x00")
        assert result == ""

    @pytest.mark.asyncio
    async def test_provider_exception_returns_empty(self):
        provider = MagicMock()
        provider.transcribe.side_effect = RuntimeError("model crashed")
        audio_mod.set_stt_provider(provider)
        result = await audio_mod._run_transcription(b"\x00\x00")
        assert result == ""

    @pytest.mark.asyncio
    async def test_provider_returns_text(self):
        provider = MagicMock()
        provider.transcribe.return_value = "hello world"
        audio_mod.set_stt_provider(provider)
        result = await audio_mod._run_transcription(b"\x00\x00")
        assert result == "hello world"
