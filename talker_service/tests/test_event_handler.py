"""Tests for event handler (v2 payload format with ConversationManager)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.handlers import events


@pytest.fixture
def mock_conversation_manager():
    """Mock ConversationManager that returns speaker + dialogue."""
    manager = MagicMock()
    manager.handle_event = AsyncMock(return_value=("char_001", "Test dialogue here"))
    return manager


@pytest.fixture
def sample_v2_payload():
    """Sample v2 game.event payload."""
    return {
        "event": {
            "type": 0,  # DEATH
            "context": {
                "actor": {
                    "game_id": "char_001",
                    "name": "Duty Soldier",
                    "faction": "dolg",
                    "rank": 450,
                },
                "victim": {
                    "game_id": "char_002",
                    "name": "Freedom Fighter",
                    "faction": "freedom",
                    "rank": 380,
                },
            },
            "timestamp": 1234567890,
        },
        "candidates": [
            {
                "game_id": "char_001",
                "name": "Duty Soldier",
                "faction": "dolg",
                "rank": 450,
            },
            {
                "game_id": "char_003",
                "name": "Duty Patrol",
                "faction": "dolg",
                "rank": 320,
            },
        ],
        "world": "Location: Garbage. Time: 14:35 (afternoon). Weather: Clear.",
        "traits": {
            "char_001": {
                "personality_id": "duty_zealot",
                "backstory_id": "duty_recruit",
            },
            "char_003": {
                "personality_id": "duty_soldier",
                "backstory_id": "generic_patrol",
            },
        },
    }


class TestHandleGameEvent:
    """Tests for handle_game_event with v2 payload."""
    
    @pytest.mark.asyncio
    async def test_parse_v2_payload(self, sample_v2_payload, mock_conversation_manager):
        """Test that v2 payload is parsed correctly."""
        events._conversation_manager = mock_conversation_manager
        
        await events.handle_game_event(sample_v2_payload, session_id="test_session", req_id=123)
        
        # Allow background task to execute
        import asyncio
        await asyncio.sleep(0.1)
        
        # Verify ConversationManager was called with correct parameters
        mock_conversation_manager.handle_event.assert_called_once()
        call_args = mock_conversation_manager.handle_event.call_args[1]
        
        assert call_args["event"] == sample_v2_payload["event"]
        assert call_args["candidates"] == sample_v2_payload["candidates"]
        assert call_args["world"] == sample_v2_payload["world"]
        assert call_args["traits"] == sample_v2_payload["traits"]
    
    @pytest.mark.asyncio
    async def test_empty_event_data(self, mock_conversation_manager):
        """Test that empty event data is rejected."""
        events._conversation_manager = mock_conversation_manager
        
        payload = {
            "event": {},
            "candidates": [],
            "world": "",
            "traits": {},
        }
        
        await events.handle_game_event(payload, req_id=124)
        
        # Allow background task to execute
        import asyncio
        await asyncio.sleep(0.1)
        
        # Should not call ConversationManager with empty event
        mock_conversation_manager.handle_event.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_no_candidates(self, sample_v2_payload, mock_conversation_manager):
        """Test that events with no candidates are skipped."""
        events._conversation_manager = mock_conversation_manager
        
        payload = sample_v2_payload.copy()
        payload["candidates"] = []
        
        await events.handle_game_event(payload, req_id=125)
        
        # Allow background task to execute
        import asyncio
        await asyncio.sleep(0.1)
        
        # Should not call ConversationManager with no candidates
        mock_conversation_manager.handle_event.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_conversation_manager_not_available(self, sample_v2_payload):
        """Test graceful handling when ConversationManager is not injected."""
        events._conversation_manager = None
        
        # Should not raise exception
        await events.handle_game_event(sample_v2_payload, req_id=126)
        
        # Allow background task to execute
        import asyncio
        await asyncio.sleep(0.1)
    
    @pytest.mark.asyncio
    async def test_logs_event_details(self, sample_v2_payload, mock_conversation_manager):
        """Test that event details are logged."""
        events._conversation_manager = mock_conversation_manager
        
        with patch("talker_service.handlers.events.logger") as mock_logger:
            await events.handle_game_event(sample_v2_payload, session_id="test", req_id=127)
        
        # Allow background task to execute
        import asyncio
        await asyncio.sleep(0.1)
        
        # Check that logger.info was called with event details
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Game Event (v2): type=0" in call for call in info_calls)
        assert any("candidates=2" in call for call in info_calls)


class TestHandleEventV2:
    """Tests for _handle_event_v2 function."""
    
    @pytest.mark.asyncio
    async def test_calls_conversation_manager(self, sample_v2_payload, mock_conversation_manager):
        """Test that _handle_event_v2 calls ConversationManager correctly."""
        events._conversation_manager = mock_conversation_manager
        
        await events._handle_event_v2(
            event=sample_v2_payload["event"],
            candidates=sample_v2_payload["candidates"],
            world=sample_v2_payload["world"],
            traits=sample_v2_payload["traits"],
            session_id="test",
            req_id=128,
        )
        
        # Verify ConversationManager.handle_event was called
        mock_conversation_manager.handle_event.assert_called_once_with(
            event=sample_v2_payload["event"],
            candidates=sample_v2_payload["candidates"],
            world=sample_v2_payload["world"],
            traits=sample_v2_payload["traits"],
            session_id="test",
        )
    
    @pytest.mark.asyncio
    async def test_returns_speaker_and_dialogue(self, sample_v2_payload, mock_conversation_manager):
        """Test that speaker and dialogue are logged."""
        events._conversation_manager = mock_conversation_manager
        mock_conversation_manager.handle_event.return_value = ("char_001", "Freedom scum eliminated!")
        
        with patch("talker_service.handlers.events.logger") as mock_logger:
            await events._handle_event_v2(
                event=sample_v2_payload["event"],
                candidates=sample_v2_payload["candidates"],
                world=sample_v2_payload["world"],
                traits=sample_v2_payload["traits"],
                req_id=129,
            )
        
        # Check that logger was called with speaker and dialogue
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Dialogue generated: speaker=char_001" in call for call in info_calls)
        assert any("Freedom scum eliminated" in call for call in info_calls)
    
    @pytest.mark.asyncio
    async def test_handles_conversation_manager_exception(self, sample_v2_payload, mock_conversation_manager):
        """Test that exceptions from ConversationManager are caught and logged."""
        events._conversation_manager = mock_conversation_manager
        mock_conversation_manager.handle_event.side_effect = Exception("LLM timeout")
        
        with patch("talker_service.handlers.events.logger") as mock_logger:
            await events._handle_event_v2(
                event=sample_v2_payload["event"],
                candidates=sample_v2_payload["candidates"],
                world=sample_v2_payload["world"],
                traits=sample_v2_payload["traits"],
                req_id=130,
            )
        
        # Check that error was logged (using logger.opt(exception=True).error())
        # The mock_logger.opt() returns a chained logger, need to check .error calls
        assert mock_logger.opt.called
        opt_logger = mock_logger.opt.return_value
        error_calls = [str(call) for call in opt_logger.error.call_args_list]
        assert any("Failed to generate dialogue:" in call for call in error_calls)
    
    @pytest.mark.asyncio
    async def test_respects_semaphore_limit(self, sample_v2_payload, mock_conversation_manager):
        """Test that semaphore prevents too many concurrent tasks."""
        events._conversation_manager = mock_conversation_manager
        
        # Lock the semaphore
        events._dialogue_semaphore._value = 0
        
        try:
            await events._handle_event_v2(
                event=sample_v2_payload["event"],
                candidates=sample_v2_payload["candidates"],
                world=sample_v2_payload["world"],
                traits=sample_v2_payload["traits"],
                req_id=131,
            )
            
            # Should not call ConversationManager when semaphore is locked
            mock_conversation_manager.handle_event.assert_not_called()
        finally:
            # Reset semaphore
            events._dialogue_semaphore._value = events._MAX_CONCURRENT_DIALOGUES


class TestSetConversationManager:
    """Tests for set_conversation_manager dependency injection."""
    
    def test_injection(self, mock_conversation_manager):
        """Test that ConversationManager can be injected."""
        events.set_conversation_manager(mock_conversation_manager)
        
        assert events._conversation_manager == mock_conversation_manager
    
    def test_logs_injection(self, mock_conversation_manager):
        """Test that injection is logged."""
        with patch("talker_service.handlers.events.logger") as mock_logger:
            events.set_conversation_manager(mock_conversation_manager)
        
        # Check that logger.info was called with injection message
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Conversation manager injected into event handlers" in call for call in info_calls)


class TestHandlePlayerDialogue:
    """Tests for handle_player_dialogue with v1 and v2 payloads."""
    
    @pytest.mark.asyncio
    async def test_v1_payload_logs_only(self):
        """Test that v1 payload (text + context) just logs."""
        v1_payload = {
            "text": "Hello nearby NPCs",
            "context": {"player_location": "Garbage"},
        }
        
        with patch("talker_service.handlers.events.logger") as mock_logger:
            await events.handle_player_dialogue(v1_payload, session_id="test", req_id=200)
        
        # Should log the text
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Player Dialogue:" in call and "Hello nearby NPCs" in call for call in info_calls)
    
    @pytest.mark.asyncio
    async def test_v2_payload_calls_conversation_manager(self, sample_v2_payload, mock_conversation_manager):
        """Test that v2 payload calls ConversationManager."""
        events._conversation_manager = mock_conversation_manager
        
        # Create a v2 player dialogue payload
        player_dialogue_v2 = {
            "event": {
                "type": "PLAYER_DIALOGUE",
                "context": {"text": "Hello everyone"},
                "timestamp": 1234567890,
            },
            "candidates": sample_v2_payload["candidates"],
            "world": "Location: Garbage. Time: 14:35.",
            "traits": sample_v2_payload.get("traits", {}),
        }
        
        await events.handle_player_dialogue(player_dialogue_v2, session_id="test", req_id=201)
        
        # Allow background task to execute
        import asyncio
        await asyncio.sleep(0.1)
        
        # ConversationManager should have been called
        mock_conversation_manager.handle_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_v2_payload_no_candidates_skips(self, mock_conversation_manager):
        """Test that v2 payload with no candidates skips processing."""
        events._conversation_manager = mock_conversation_manager
        
        player_dialogue_v2 = {
            "event": {"type": "PLAYER_DIALOGUE", "context": {"text": "Hello"}, "timestamp": 123},
            "candidates": [],  # No candidates
            "world": "Location: Garbage.",
            "traits": {},
        }
        
        await events.handle_player_dialogue(player_dialogue_v2, session_id="test", req_id=202)
        
        # Allow background task to execute
        import asyncio
        await asyncio.sleep(0.1)
        
        # ConversationManager should NOT be called (no candidates)
        mock_conversation_manager.handle_event.assert_not_called()


class TestHandlePlayerWhisper:
    """Tests for handle_player_whisper with v1 and v2 payloads."""
    
    @pytest.mark.asyncio
    async def test_v1_payload_logs_only(self):
        """Test that v1 payload (text + target) just logs."""
        v1_payload = {
            "text": "Hey Sidorovich",
            "target": {
                "game_id": "sid",
                "name": "Sidorovich",
                "faction": "trader",
            },
        }
        
        with patch("talker_service.handlers.events.logger") as mock_logger:
            await events.handle_player_whisper(v1_payload, session_id="test", req_id=300)
        
        # Should log the text
        info_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any("Player Whisper:" in call and "Hey Sidorovich" in call for call in info_calls)
    
    @pytest.mark.asyncio
    async def test_v2_payload_calls_conversation_manager(self, sample_v2_payload, mock_conversation_manager):
        """Test that v2 payload calls ConversationManager."""
        events._conversation_manager = mock_conversation_manager
        
        # Create a v2 player whisper payload
        player_whisper_v2 = {
            "event": {
                "type": "PLAYER_WHISPER",
                "context": {"text": "Need help here"},
                "timestamp": 1234567890,
            },
            "candidates": sample_v2_payload["candidates"],
            "world": "Location: Garbage. Time: 14:35.",
            "traits": sample_v2_payload.get("traits", {}),
        }
        
        await events.handle_player_whisper(player_whisper_v2, session_id="test", req_id=301)
        
        # Allow background task to execute
        import asyncio
        await asyncio.sleep(0.1)
        
        # ConversationManager should have been called
        mock_conversation_manager.handle_event.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_v2_payload_no_candidates_skips(self, mock_conversation_manager):
        """Test that v2 payload with no candidates skips processing."""
        events._conversation_manager = mock_conversation_manager
        
        player_whisper_v2 = {
            "event": {"type": "PLAYER_WHISPER", "context": {"text": "Help"}, "timestamp": 123},
            "candidates": [],  # No candidates
            "world": "Location: Garbage.",
            "traits": {},
        }
        
        await events.handle_player_whisper(player_whisper_v2, session_id="test", req_id=302)
        
        # Allow background task to execute
        import asyncio
        await asyncio.sleep(0.1)
        
        # ConversationManager should NOT be called (no candidates)
        mock_conversation_manager.handle_event.assert_not_called()


class TestNeo4jIngestFlow:
    @pytest.mark.asyncio
    async def test_ingest_task_scheduled_before_dialogue(self, sample_v2_payload, mock_conversation_manager, monkeypatch):
        events._conversation_manager = mock_conversation_manager

        class _Neo4j:
            def is_available(self):
                return True

            def has_event_embedding(self, _ts, _cs):
                return False

            def ingest_event(self, *_args, **_kwargs):
                return True

        events._neo4j_client = _Neo4j()
        events._embedding_client = None

        scheduled = []

        def _fake_logged_task(coro, *, name="unnamed"):
            scheduled.append(name)
            coro.close()
            return None

        monkeypatch.setattr(events, "_logged_task", _fake_logged_task)

        await events.handle_game_event(sample_v2_payload, session_id="s1", req_id=900)

        assert len(scheduled) == 2
        assert scheduled[0].startswith("ingest-")
        assert scheduled[1].startswith("dialogue-")

    @pytest.mark.asyncio
    async def test_index_only_skips_dialogue(self, sample_v2_payload, mock_conversation_manager, monkeypatch):
        events._conversation_manager = mock_conversation_manager

        class _Neo4j:
            def is_available(self):
                return True

            def has_event_embedding(self, _ts, _cs):
                return False

            def ingest_event(self, *_args, **_kwargs):
                return True

        events._neo4j_client = _Neo4j()
        events._embedding_client = None

        scheduled = []

        def _fake_logged_task(coro, *, name="unnamed"):
            scheduled.append(name)
            coro.close()
            return None

        monkeypatch.setattr(events, "_logged_task", _fake_logged_task)

        payload = dict(sample_v2_payload)
        payload["event"] = dict(sample_v2_payload["event"])
        payload["event"]["flags"] = {"index_only": True}

        await events.handle_game_event(payload, session_id="s1", req_id=901)

        assert len(scheduled) == 1
        assert scheduled[0].startswith("ingest-")

    @pytest.mark.asyncio
    async def test_ingest_failure_is_non_blocking(self, sample_v2_payload):
        class _FailingNeo4j:
            def is_available(self):
                return True

            def has_event_embedding(self, _ts, _cs):
                raise RuntimeError("boom")

            def ingest_event(self, *_args, **_kwargs):
                raise RuntimeError("boom")

        events._neo4j_client = _FailingNeo4j()
        events._embedding_client = AsyncMock()

        # Should not raise despite neo4j client failures.
        await events._ingest_event(
            sample_v2_payload["event"],
            ingest_session_id="lua-session-1",
            player_id="player1",
            branch="main",
            req_id=902,
            connection_session_id="conn-1",
        )

    @pytest.mark.asyncio
    async def test_duplicate_event_skips_reembedding(self, sample_v2_payload):
        class _Neo4j:
            def __init__(self):
                self.ingest_calls = 0

            def is_available(self):
                return True

            def has_event_embedding(self, _ts, _cs):
                return True

            def ingest_event(self, *_args, **_kwargs):
                self.ingest_calls += 1
                return True

        neo4j = _Neo4j()
        embed_client = AsyncMock()

        events._neo4j_client = neo4j
        events._embedding_client = embed_client

        await events._ingest_event(
            sample_v2_payload["event"],
            ingest_session_id="lua-session-1",
            player_id="player1",
            branch="main",
            req_id=903,
            connection_session_id="conn-1",
        )

        assert neo4j.ingest_calls == 1
        embed_client.embed.assert_not_awaited()
