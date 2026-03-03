"""Tests for TTS dialogue dispatch in event handlers."""

import asyncio
import base64

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.handlers import events


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_events_globals():
    """Reset module-level globals before each test."""
    events._conversation_manager = None
    events._publisher = None
    events._tts_engine = None
    events._dialogue_id = 0
    yield
    events._conversation_manager = None
    events._publisher = None
    events._tts_engine = None
    events._dialogue_id = 0


@pytest.fixture
def mock_publisher():
    pub = MagicMock()
    pub.publish = AsyncMock(return_value=True)
    return pub


@pytest.fixture
def mock_tts_engine():
    """TTS engine mock that returns OGG bytes + duration."""
    engine = MagicMock()
    engine.generate_audio = AsyncMock(return_value=(b"\x00OGG_FAKE", 2500))
    return engine


@pytest.fixture
def candidates():
    """Two candidates with sound_prefix."""
    return [
        {"game_id": "5", "name": "Duty Guard", "faction": "dolg", "sound_prefix": "dolg_1"},
        {"game_id": "9", "name": "Freedom Scout", "faction": "freedom", "sound_prefix": "freedom_2"},
    ]


@pytest.fixture
def candidates_no_prefix():
    """Candidate without sound_prefix."""
    return [
        {"game_id": "5", "name": "Duty Guard", "faction": "dolg"},
    ]


# ---------------------------------------------------------------------------
# 3.1  set_tts_engine() injection & None default
# ---------------------------------------------------------------------------

class TestSetTtsEngine:
    def test_default_is_none(self):
        assert events._tts_engine is None

    def test_inject_engine(self, mock_tts_engine):
        events.set_tts_engine(mock_tts_engine)
        assert events._tts_engine is mock_tts_engine

    def test_inject_none(self):
        engine = MagicMock()
        events.set_tts_engine(engine)
        assert events._tts_engine is engine
        events.set_tts_engine(None)
        assert events._tts_engine is None


# ---------------------------------------------------------------------------
# 3.2  voice_id resolved from candidates
# ---------------------------------------------------------------------------

class TestVoiceIdResolution:
    @pytest.mark.asyncio
    async def test_exact_match(self, mock_publisher, mock_tts_engine, candidates):
        """Speaker found in candidates — voice_id comes from sound_prefix."""
        events._publisher = mock_publisher
        events._tts_engine = mock_tts_engine

        await events._dispatch_dialogue(
            speaker_id="5",
            dialogue_text="Stay sharp.",
            voice_id="dolg_1",  # pre-resolved
            dialogue_id=1,
            session_id="s1",
            pfx="[test] ",
        )

        mock_tts_engine.generate_audio.assert_awaited_once_with("Stay sharp.", "dolg_1")

    @pytest.mark.asyncio
    async def test_missing_prefix_passes_empty(self, mock_publisher, mock_tts_engine, candidates_no_prefix):
        """Candidate has no sound_prefix — voice_id should be empty string."""
        events._publisher = mock_publisher
        events._tts_engine = mock_tts_engine

        await events._dispatch_dialogue(
            speaker_id="5",
            dialogue_text="Hello.",
            voice_id="",  # pre-resolved to empty (no sound_prefix)
            dialogue_id=1,
            session_id="s1",
            pfx="[test] ",
        )

        mock_tts_engine.generate_audio.assert_awaited_once_with("Hello.", "")

    @pytest.mark.asyncio
    async def test_voice_id_resolved_in_handle_event_v2(self, mock_publisher, mock_tts_engine, candidates):
        """Integration: _handle_event_v2 resolves voice_id from candidates."""
        cm = MagicMock()
        cm.handle_event = AsyncMock(return_value=("5", "Watch your step."))
        events._conversation_manager = cm
        events._publisher = mock_publisher
        events._tts_engine = mock_tts_engine

        await events._handle_event_v2(
            event={"type": 0, "context": {}, "timestamp": 0},
            candidates=candidates,
            world="",
            traits={},
            session_id="s1",
        )

        # TTS should have been called with dolg_1 (sound_prefix for game_id=5)
        mock_tts_engine.generate_audio.assert_awaited_once()
        call_args = mock_tts_engine.generate_audio.call_args
        assert call_args[0][1] == "dolg_1"  # voice_id argument

    @pytest.mark.asyncio
    async def test_llm_changed_speaker_resolves_correct_prefix(self, mock_publisher, mock_tts_engine, candidates):
        """LLM picked a different speaker — voice_id comes from that speaker."""
        cm = MagicMock()
        cm.handle_event = AsyncMock(return_value=("9", "Freedom forever."))
        events._conversation_manager = cm
        events._publisher = mock_publisher
        events._tts_engine = mock_tts_engine

        await events._handle_event_v2(
            event={"type": 0, "context": {}, "timestamp": 0},
            candidates=candidates,
            world="",
            traits={},
            session_id="s1",
        )

        call_args = mock_tts_engine.generate_audio.call_args
        assert call_args[0][1] == "freedom_2"


# ---------------------------------------------------------------------------
# 3.3  TTS dispatch publishes tts.audio
# ---------------------------------------------------------------------------

class TestTtsDispatchSuccess:
    @pytest.mark.asyncio
    async def test_publishes_tts_audio(self, mock_publisher, mock_tts_engine):
        """Successful TTS generation publishes tts.audio with correct payload."""
        events._publisher = mock_publisher
        events._tts_engine = mock_tts_engine

        await events._dispatch_dialogue(
            speaker_id="5",
            dialogue_text="Stay sharp.",
            voice_id="dolg_1",
            dialogue_id=1,
            session_id="s1",
            pfx="[test] ",
        )

        mock_publisher.publish.assert_awaited_once()
        topic, payload = mock_publisher.publish.call_args[0]
        kwargs = mock_publisher.publish.call_args[1]

        assert topic == "tts.audio"
        assert payload["speaker_id"] == "5"
        assert payload["dialogue"] == "Stay sharp."
        assert payload["voice_id"] == "dolg_1"
        assert payload["dialogue_id"] == 1
        assert payload["create_event"] is True
        assert "audio_b64" in payload
        assert payload["duration_ms"] == 2500
        assert kwargs["session"] == "s1"

        # Verify base64 decodes to the original bytes
        decoded = base64.b64decode(payload["audio_b64"])
        assert decoded == b"\x00OGG_FAKE"


# ---------------------------------------------------------------------------
# 3.4  Fallback to dialogue.display when engine returns None or raises
# ---------------------------------------------------------------------------

class TestTtsFallback:
    @pytest.mark.asyncio
    async def test_fallback_when_engine_returns_none(self, mock_publisher):
        """TTS returns None — should publish dialogue.display instead."""
        engine = MagicMock()
        engine.generate_audio = AsyncMock(return_value=None)
        events._publisher = mock_publisher
        events._tts_engine = engine

        await events._dispatch_dialogue(
            speaker_id="5",
            dialogue_text="Hmm.",
            voice_id="dolg_1",
            dialogue_id=1,
            session_id="s1",
            pfx="[test] ",
        )

        topic, payload = mock_publisher.publish.call_args[0]
        assert topic == "dialogue.display"
        assert payload["speaker_id"] == "5"
        assert payload["dialogue"] == "Hmm."
        assert "audio_b64" not in payload

    @pytest.mark.asyncio
    async def test_fallback_when_engine_raises(self, mock_publisher):
        """TTS raises an exception — should fall back to dialogue.display."""
        engine = MagicMock()
        engine.generate_audio = AsyncMock(side_effect=RuntimeError("TTS boom"))
        events._publisher = mock_publisher
        events._tts_engine = engine

        await events._dispatch_dialogue(
            speaker_id="5",
            dialogue_text="Hmm.",
            voice_id="dolg_1",
            dialogue_id=1,
            session_id="s1",
            pfx="[test] ",
        )

        topic, payload = mock_publisher.publish.call_args[0]
        assert topic == "dialogue.display"
        assert payload["dialogue"] == "Hmm."


# ---------------------------------------------------------------------------
# 3.5  Fallback when no TTS engine injected
# ---------------------------------------------------------------------------

class TestNoTtsEngine:
    @pytest.mark.asyncio
    async def test_publishes_dialogue_display_when_no_engine(self, mock_publisher):
        """No TTS engine injected — always publishes dialogue.display."""
        events._publisher = mock_publisher
        events._tts_engine = None

        await events._dispatch_dialogue(
            speaker_id="5",
            dialogue_text="All quiet.",
            voice_id="dolg_1",
            dialogue_id=1,
            session_id="s1",
            pfx="[test] ",
        )

        topic, payload = mock_publisher.publish.call_args[0]
        assert topic == "dialogue.display"
        assert payload["speaker_id"] == "5"
        assert payload["dialogue"] == "All quiet."
        assert payload["dialogue_id"] == 1
        assert "audio_b64" not in payload


# ---------------------------------------------------------------------------
# 3.6  Monotonic dialogue_id increments across dispatches
# ---------------------------------------------------------------------------

class TestDialogueId:
    @pytest.mark.asyncio
    async def test_increments_across_dispatches(self, mock_publisher):
        """dialogue_id increments with each dispatch through _handle_event_v2."""
        cm = MagicMock()
        cm.handle_event = AsyncMock(return_value=("5", "Line"))
        events._conversation_manager = cm
        events._publisher = mock_publisher
        events._tts_engine = None

        candidates = [{"game_id": "5", "name": "X", "sound_prefix": "s"}]
        for _ in range(3):
            await events._handle_event_v2(
                event={"type": 0, "context": {}, "timestamp": 0},
                candidates=candidates,
                world="",
                traits={},
                session_id="s1",
            )

        # Should have 3 calls, dialogue_ids 1, 2, 3
        assert mock_publisher.publish.await_count == 3
        ids = [
            mock_publisher.publish.call_args_list[i][0][1]["dialogue_id"]
            for i in range(3)
        ]
        assert ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_dialogue_id_in_tts_audio_payload(self, mock_publisher, mock_tts_engine):
        """dialogue_id appears in tts.audio payload."""
        events._publisher = mock_publisher
        events._tts_engine = mock_tts_engine

        await events._dispatch_dialogue(
            speaker_id="5",
            dialogue_text="Go.",
            voice_id="v",
            dialogue_id=42,
            session_id="s1",
            pfx="",
        )

        payload = mock_publisher.publish.call_args[0][1]
        assert payload["dialogue_id"] == 42

    @pytest.mark.asyncio
    async def test_dialogue_id_in_display_payload(self, mock_publisher):
        """dialogue_id appears in dialogue.display payload."""
        events._publisher = mock_publisher
        events._tts_engine = None

        await events._dispatch_dialogue(
            speaker_id="5",
            dialogue_text="Go.",
            voice_id="v",
            dialogue_id=7,
            session_id="s1",
            pfx="",
        )

        payload = mock_publisher.publish.call_args[0][1]
        assert payload["dialogue_id"] == 7
