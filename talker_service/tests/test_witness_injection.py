"""Tests for witness event injection and build_witness_text helper."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from talker_service.dialogue.conversation import (
    build_witness_text,
    ConversationManager,
)


# ---------------------------------------------------------------------------
# Task 1.5 — build_witness_text unit tests
# ---------------------------------------------------------------------------

class TestBuildWitnessText:
    """Unit tests for the build_witness_text() helper."""

    def test_death_event_with_actor_and_victim(self):
        """DEATH event: 'Witnessed: DEATH — Wolf killed Bandit_7'."""
        event = {
            "type": "death",
            "context": {
                "actor": {"name": "Wolf", "faction": "stalker"},
                "victim": {"name": "Bandit_7", "faction": "bandit"},
            },
        }
        assert build_witness_text(event) == "Witnessed: DEATH — Wolf killed Bandit_7"

    def test_idle_event_actor_only(self):
        """IDLE event with only actor: 'Witnessed: IDLE — Fanatic'."""
        event = {
            "type": "idle",
            "context": {
                "actor": {"name": "Fanatic", "faction": "dolg"},
            },
        }
        assert build_witness_text(event) == "Witnessed: IDLE — Fanatic"

    def test_unknown_event_type_normalised(self):
        """Unknown string event type is uppercased."""
        event = {
            "type": "new_weather",
            "context": {
                "actor": {"name": "Loner"},
            },
        }
        assert build_witness_text(event) == "Witnessed: NEW_WEATHER — Loner"

    def test_numeric_event_type(self):
        """Numeric event type 0 maps to DEATH."""
        event = {
            "type": 0,
            "context": {
                "actor": {"name": "Wolf"},
                "victim": {"name": "Boar"},
            },
        }
        assert build_witness_text(event) == "Witnessed: DEATH — Wolf killed Boar"

    def test_injury_event_uses_injured_verb(self):
        """INJURY event uses 'injured' verb."""
        event = {
            "type": "injury",
            "context": {
                "actor": {"name": "Merc"},
                "victim": {"name": "Bandit"},
            },
        }
        assert build_witness_text(event) == "Witnessed: INJURY — Merc injured Bandit"

    def test_no_actor_no_victim(self):
        """Event with no actor/victim → just type."""
        event = {"type": "emission", "context": {}}
        assert build_witness_text(event) == "Witnessed: EMISSION"

    def test_missing_context(self):
        """Event with no context key at all."""
        event = {"type": "death"}
        assert build_witness_text(event) == "Witnessed: DEATH"

    def test_killer_fallback_alias(self):
        """'killer' key used when 'actor' is absent."""
        event = {
            "type": "death",
            "context": {
                "killer": {"name": "Sniper"},
                "victim": {"name": "Bandit_3"},
            },
        }
        assert build_witness_text(event) == "Witnessed: DEATH — Sniper killed Bandit_3"

    def test_actor_and_victim_with_unknown_event(self):
        """Unknown event with actor + victim uses 'affected' verb."""
        event = {
            "type": "strange_event",
            "context": {
                "actor": {"name": "Alpha"},
                "victim": {"name": "Beta"},
            },
        }
        assert build_witness_text(event) == "Witnessed: STRANGE_EVENT — Alpha affected Beta"


# ---------------------------------------------------------------------------
# Task 5.1 — Integration test: witness injection via mutate_batch
# ---------------------------------------------------------------------------

class TestInjectWitnessEvents:
    """Integration-style tests for _inject_witness_events."""

    @pytest.fixture
    def mock_state_client(self):
        client = MagicMock()
        client.execute_batch = AsyncMock(return_value=MagicMock())
        client.mutate_batch = AsyncMock(return_value=True)
        return client

    @pytest.fixture
    def manager(self, mock_state_client):
        mock_llm = AsyncMock()
        return ConversationManager(
            llm_client=mock_llm,
            state_client=mock_state_client,
        )

    @pytest.mark.asyncio
    async def test_three_alive_candidates_get_witness_event(self, manager, mock_state_client):
        """3 alive candidates → mutate_batch called with 3 append mutations."""
        event = {
            "type": "death",
            "context": {
                "actor": {"name": "Wolf"},
                "victim": {"name": "Bandit_7"},
            },
        }
        candidates = [
            {"game_id": "wolf", "name": "Wolf", "is_alive": True},
            {"game_id": "fanatic", "name": "Fanatic", "is_alive": True},
            {"game_id": "loner_42", "name": "Loner_42", "is_alive": True},
        ]

        await manager._inject_witness_events(event, candidates)

        mock_state_client.mutate_batch.assert_called_once()
        mutations = mock_state_client.mutate_batch.call_args[0][0]
        assert len(mutations) == 3
        for m in mutations:
            assert m["op"] == "append"
            assert m["resource"] == "memory.events"
            assert "Witnessed: DEATH" in m["data"][0]["text"]

    @pytest.mark.asyncio
    async def test_dead_candidate_excluded(self, manager, mock_state_client):
        """Dead candidate (is_alive=False) excluded from injection."""
        event = {
            "type": "death",
            "context": {
                "actor": {"name": "Wolf"},
                "victim": {"name": "Bandit_7"},
            },
        }
        candidates = [
            {"game_id": "wolf", "name": "Wolf", "is_alive": True},
            {"game_id": "bandit_7", "name": "Bandit_7", "is_alive": False},
        ]

        await manager._inject_witness_events(event, candidates)

        mutations = mock_state_client.mutate_batch.call_args[0][0]
        assert len(mutations) == 1
        assert mutations[0]["params"]["character_id"] == "wolf"

    @pytest.mark.asyncio
    async def test_all_dead_candidates_no_injection(self, manager, mock_state_client):
        """All candidates dead → no mutate_batch call."""
        event = {"type": "death", "context": {}}
        candidates = [
            {"game_id": "a", "is_alive": False},
            {"game_id": "b", "is_alive": False},
        ]

        await manager._inject_witness_events(event, candidates)

        mock_state_client.mutate_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_mutation_failure_logged_not_fatal(self, manager, mock_state_client):
        """mutate_batch failure is logged but does not raise."""
        mock_state_client.mutate_batch.side_effect = Exception("WS timeout")

        event = {"type": "idle", "context": {"actor": {"name": "X"}}}
        candidates = [{"game_id": "x", "is_alive": True}]

        # Should not raise
        await manager._inject_witness_events(event, candidates)

    @pytest.mark.asyncio
    async def test_is_alive_defaults_true_when_absent(self, manager, mock_state_client):
        """Candidates without is_alive field are treated as alive."""
        event = {"type": "idle", "context": {"actor": {"name": "Y"}}}
        candidates = [{"game_id": "y", "name": "Y"}]  # no is_alive key

        await manager._inject_witness_events(event, candidates)

        mutations = mock_state_client.mutate_batch.call_args[0][0]
        assert len(mutations) == 1
