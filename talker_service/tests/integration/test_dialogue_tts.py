"""Integration tests for dialogue generation with TTS audio."""

import base64
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.dialogue import DialogueGenerator
from talker_service.state.client import StateQueryClient
from talker_service.state.batch import BatchResult
from talker_service.llm import LLMClient


def _make_batch_result() -> BatchResult:
    """Create a BatchResult with standard test data."""
    return BatchResult({
        "mem": {"ok": True, "data": {"narrative": None, "last_update_time_ms": 0}},
        "events": {"ok": True, "data": []},
        "char": {"ok": True, "data": {
            "game_id": "12345",
            "name": "Wolf",
            "faction": "stalker",
            "sound_prefix": "stalker_1",
        }},
        "world": {"ok": True, "data": {
            "loc": "l01_escape",
            "poi": "Rookie Village",
            "time": {"Y": 2012, "M": 6, "D": 15, "h": 14, "m": 30},
            "weather": "clear",
        }},
        "personality": {"ok": True, "data": {"12345": "gruff_but_fair"}},
        "backstory": {"ok": True, "data": {}},
        "alive": {"ok": True, "data": {}},
    })


class TestDialogueTTS:
    """Test dialogue generation with TTS audio integration."""

    @pytest.mark.asyncio
    async def test_tts_enabled_publishes_audio(self):
        """When TTS engine available, publishes tts.audio instead of dialogue.display."""
        
        # Setup mocks
        llm_mock = AsyncMock(spec=LLMClient)
        llm_mock.complete = AsyncMock(return_value="Test dialogue response")
        
        state_mock = AsyncMock(spec=StateQueryClient)
        state_mock.execute_batch = AsyncMock(return_value=_make_batch_result())
        
        publisher_mock = AsyncMock()
        publisher_mock.publish = AsyncMock(return_value=True)
        
        # Mock TTS engine
        tts_mock = MagicMock()
        fake_audio = b'\x00\x01\x02\x03'  # Fake OGG data
        tts_mock.generate_audio = AsyncMock(return_value=(fake_audio, 1234))
        
        # Create generator with TTS engine
        generator = DialogueGenerator(
            llm_client=llm_mock,
            state_client=state_mock,
            publisher=publisher_mock,
            tts_engine=tts_mock,
        )
        
        # Generate dialogue
        event = {
            "type": "DEATH",
            "context": {
                "actor": {
                    "game_id": 12345,
                    "name": "Wolf",
                    "faction": "stalker",
                },
                "victim": {
                    "game_id": 99999,
                    "name": "a Pseudodog",
                    "faction": "monster",
                },
            },
            "game_time_ms": 3000000,
            "witnesses": [
                {
                    "game_id": 12345,
                    "name": "Wolf",
                    "faction": "stalker",
                }
            ],
            "flags": {},
        }
        
        await generator.generate_from_instruction("12345", event)
        
        # Verify TTS engine was called with correct kwargs
        tts_mock.generate_audio.assert_called_once()
        call_args = tts_mock.generate_audio.call_args
        assert call_args.kwargs["text"] == "Test dialogue response"
        assert call_args.kwargs["voice_id"] == "stalker_1"
        
        # Verify tts.audio was published (NOT dialogue.display)
        publisher_mock.publish.assert_called_once()
        topic, payload = publisher_mock.publish.call_args[0]
        assert topic == "tts.audio"
        assert payload["speaker_id"] == "12345"
        assert payload["dialogue"] == "Test dialogue response"
        assert "audio_b64" in payload
        assert payload["voice_id"] == "stalker_1"
        assert payload["audio_duration_ms"] == 1234
        
        # Verify audio is base64 encoded
        audio_base64 = payload["audio_b64"]
        decoded = base64.b64decode(audio_base64)
        assert decoded == fake_audio

    @pytest.mark.asyncio
    async def test_tts_failure_falls_back_to_display(self):
        """When TTS generation fails, falls back to dialogue.display."""
        
        # Setup mocks
        llm_mock = AsyncMock(spec=LLMClient)
        llm_mock.complete = AsyncMock(return_value="Test dialogue response")
        
        state_mock = AsyncMock(spec=StateQueryClient)
        state_mock.execute_batch = AsyncMock(return_value=_make_batch_result())
        
        publisher_mock = AsyncMock()
        publisher_mock.publish = AsyncMock(return_value=True)
        
        # Mock TTS engine that raises exception
        tts_mock = MagicMock()
        tts_mock.generate_audio = AsyncMock(side_effect=RuntimeError("TTS failed"))
        
        # Create generator with TTS engine
        generator = DialogueGenerator(
            llm_client=llm_mock,
            state_client=state_mock,
            publisher=publisher_mock,
            tts_engine=tts_mock,
        )
        
        # Generate dialogue
        event = {
            "type": "DEATH",
            "context": {
                "actor": {
                    "game_id": 12345,
                    "name": "Wolf",
                    "faction": "stalker",
                },
                "victim": {
                    "game_id": 99999,
                    "name": "a Pseudodog",
                    "faction": "monster",
                },
            },
            "game_time_ms": 3000000,
            "witnesses": [
                {
                    "game_id": 12345,
                    "name": "Wolf",
                    "faction": "stalker",
                }
            ],
            "flags": {},
        }
        
        await generator.generate_from_instruction("12345", event)
        
        # Verify TTS engine was called but failed
        tts_mock.generate_audio.assert_called_once()
        
        # Verify dialogue.display was published as fallback
        publisher_mock.publish.assert_called_once()
        topic, payload = publisher_mock.publish.call_args[0]
        assert topic == "dialogue.display"
        assert payload["speaker_id"] == "12345"
        assert payload["dialogue"] == "Test dialogue response"
        assert "audio_b64" not in payload  # No audio field in fallback

    @pytest.mark.asyncio
    async def test_no_tts_engine_uses_display(self):
        """When TTS engine not provided, uses dialogue.display."""
        
        # Setup mocks
        llm_mock = AsyncMock(spec=LLMClient)
        llm_mock.complete = AsyncMock(return_value="Test dialogue response")
        
        state_mock = AsyncMock(spec=StateQueryClient)
        state_mock.execute_batch = AsyncMock(return_value=_make_batch_result())
        
        publisher_mock = AsyncMock()
        publisher_mock.publish = AsyncMock(return_value=True)
        
        # Create generator WITHOUT TTS engine
        generator = DialogueGenerator(
            llm_client=llm_mock,
            state_client=state_mock,
            publisher=publisher_mock,
            tts_engine=None,  # No TTS
        )
        
        # Generate dialogue
        event = {
            "type": "DEATH",
            "context": {
                "actor": {
                    "game_id": 12345,
                    "name": "Wolf",
                    "faction": "stalker",
                },
                "victim": {
                    "game_id": 99999,
                    "name": "a Pseudodog",
                    "faction": "monster",
                },
            },
            "game_time_ms": 3000000,
            "witnesses": [
                {
                    "game_id": 12345,
                    "name": "Wolf",
                    "faction": "stalker",
                }
            ],
            "flags": {},
        }
        
        await generator.generate_from_instruction("12345", event)
        
        # Verify dialogue.display was published
        publisher_mock.publish.assert_called_once()
        topic, payload = publisher_mock.publish.call_args[0]
        assert topic == "dialogue.display"
        assert payload["speaker_id"] == "12345"
        assert payload["dialogue"] == "Test dialogue response"
        assert "audio_b64" not in payload
