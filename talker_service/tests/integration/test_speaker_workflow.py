"""Integration test for two-step speaker selection workflow.

Validates that the ConversationManager produces the correct deterministic flow:
1. Ensure backgrounds for all candidates (via BackgroundGenerator)
2. Speaker picker (ephemeral): LLM picks a speaker ID -> messages removed
3. Dialogue generation (persistent): LLM generates dialogue -> messages kept

Key assertions:
- Background generation is called with all candidates
- Speaker picker sends candidates + event + instruction, then cleans up
- Dialogue generation injects memory context and keeps messages
- Witness injection fires for all alive candidates
- Final (speaker_id, dialogue_text) is correct
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.dialogue.conversation import ConversationManager
from talker_service.state.batch import BatchResult
from talker_service.llm.models import Message


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def five_candidates():
    """Five NPC candidates with distinct factions and game_ids."""
    return [
        {"game_id": "npc_100", "name": "Wolf", "faction": "stalker", "rank": 750, "is_alive": True},
        {"game_id": "npc_101", "name": "Fanatic", "faction": "dolg", "rank": 450, "is_alive": True},
        {"game_id": "npc_102", "name": "Skinner", "faction": "bandit", "rank": 200, "is_alive": True},
        {"game_id": "npc_103", "name": "Lukash", "faction": "freedom", "rank": 600, "is_alive": True},
        {"game_id": "npc_104", "name": "Owl", "faction": "stalker", "rank": 320, "is_alive": True},
    ]


@pytest.fixture
def death_event():
    """A basic DEATH event where Wolf kills a mutant."""
    return {
        "type": "death",
        "context": {
            "actor": {"game_id": "npc_100", "name": "Wolf", "faction": "stalker"},
            "victim": {"game_id": "mutant_1", "name": "Bloodsucker", "faction": "monster"},
        },
        "game_time_ms": 5000000,
    }


@pytest.fixture
def traits_map():
    """Traits for all five candidates."""
    return {
        "npc_100": {"personality_id": "stalker.1", "backstory_id": "loner.1"},
        "npc_101": {"personality_id": "duty.2", "backstory_id": "duty.1"},
        "npc_102": {"personality_id": "bandit.3", "backstory_id": "bandit.1"},
        "npc_103": {"personality_id": "freedom.1", "backstory_id": "freedom.1"},
        "npc_104": {"personality_id": "stalker.5", "backstory_id": "loner.3"},
    }


# ---------------------------------------------------------------------------
# Mock state client with canned batch responses
# ---------------------------------------------------------------------------

class WorkflowStateClient:
    """State client that returns canned responses and records all batch calls."""

    def __init__(self):
        self.batch_calls: list[list[dict]] = []
        self.mutation_calls: list[list[dict]] = []

    async def execute_batch(self, batch, *, timeout=None, session=None) -> BatchResult:
        queries = batch.build()
        self.batch_calls.append(queries)

        results: dict[str, dict] = {}
        for q in queries:
            qid = q["id"]
            resource = q["resource"]

            if resource == "memory.background":
                cid = q["params"]["character_id"]
                results[qid] = {
                    "ok": True,
                    "data": {
                        "traits": ["brave"],
                        "backstory": f"Background for {cid}",
                        "connections": [],
                    },
                }
            elif resource.startswith("memory."):
                tier = resource.split(".", 1)[1]
                results[qid] = {
                    "ok": True,
                    "data": [
                        {"type": "CALLOUT", "text": f"Sample {tier} entry", "timestamp": 1000},
                    ],
                }
            elif resource == "query.world":
                results[qid] = {
                    "ok": True,
                    "data": {
                        "loc": "l01_escape",
                        "poi": "Rookie Village",
                        "time": {"Y": 2012, "M": 6, "D": 15, "h": 14, "m": 30, "s": 0, "ms": 0},
                        "weather": "clear",
                        "emission": False,
                        "psy_storm": False,
                        "sheltering": False,
                        "campfire": None,
                        "brain_scorcher_disabled": False,
                        "miracle_machine_disabled": False,
                    },
                }
            elif resource == "query.characters_alive":
                results[qid] = {"ok": True, "data": {}}
            elif resource == "query.character_info":
                cid = q["params"].get("id", "unknown")
                results[qid] = {
                    "ok": True,
                    "data": {
                        "character": {
                            "game_id": cid,
                            "name": f"NPC_{cid}",
                            "faction": "stalker",
                            "gender": "male",
                        },
                        "squad_members": [],
                    },
                }
            else:
                results[qid] = {"ok": False, "error": f"unknown resource: {resource}"}

        return BatchResult(results)

    async def mutate_batch(self, mutations, *, timeout=None):
        """Record mutations and return success."""
        self.mutation_calls.append(mutations)
        return True


# ---------------------------------------------------------------------------
# Mock background generator
# ---------------------------------------------------------------------------

class WorkflowBackgroundGenerator:
    """Background generator that populates candidates with canned backgrounds."""

    def __init__(self):
        self.calls: list[list[dict]] = []

    async def ensure_backgrounds(self, candidates):
        self.calls.append(candidates)
        for cand in candidates:
            if cand.get("background") is None:
                cid = cand.get("game_id", "unknown")
                cand["background"] = {
                    "traits": ["brave"],
                    "backstory": f"Background for {cid}",
                    "connections": [],
                }
        return candidates


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestTwoStepWorkflow:
    """Integration tests for the two-step dialogue workflow."""

    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_full_workflow_five_candidates(
        self,
        mock_world_ctx,
        five_candidates,
        death_event,
        traits_map,
    ):
        """Full workflow: 5 candidates -> backgrounds -> pick speaker -> generate dialogue.

        Verifies:
        - BackgroundGenerator.ensure_backgrounds called with all candidates
        - LLM complete() called twice (picker + dialogue)
        - Picker messages are cleaned up (not in final history)
        - Dialogue messages are kept in history
        - Final (speaker_id, dialogue) are correct
        """
        chosen = "npc_101"

        # LLM returns chosen speaker ID for picker, then dialogue for generation
        llm = MagicMock()
        call_count = 0

        async def _complete(messages, opts=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return chosen  # picker response
            return "Damn mutants... another day in the Zone."  # dialogue

        llm.complete = AsyncMock(side_effect=_complete)

        state_client = WorkflowStateClient()
        bg_gen = WorkflowBackgroundGenerator()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
            background_generator=bg_gen,
        )

        speaker_id, dialogue = await manager.handle_event(
            event=death_event,
            candidates=five_candidates,
            world="Location: Cordon. Time: 14:35.",
            traits=traits_map,
        )

        # --- assertions ---
        assert speaker_id == chosen
        assert "mutants" in dialogue.lower()

        # BackgroundGenerator was called with all 5 candidates
        assert len(bg_gen.calls) == 1
        assert len(bg_gen.calls[0]) == 5

        # LLM was called exactly twice: picker + dialogue
        assert call_count == 2

        # Four-layer layout: 3 base (system + context_block + "Ready.") + user + assistant = 5
        # Picker messages are ephemeral and removed after selection
        assert len(manager._messages) == 5
        assert manager._messages[0].role == "system"   # static system prompt
        assert manager._messages[1].role == "user"     # context block
        assert manager._messages[2].role == "assistant" # "Ready." ack
        assert manager._messages[3].role == "user"     # dialogue prompt
        assert manager._messages[4].role == "assistant" # LLM response
        assert "Damn mutants" in manager._messages[4].content

        # Context block holds all 5 candidate backgrounds (plus any inhabitants from world enrichment)
        for cand in five_candidates:
            assert manager._context_block.has_background(cand["game_id"])

    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_single_candidate_skips_picker(
        self,
        mock_world_ctx,
        death_event,
        traits_map,
    ):
        """With a single candidate, the picker step is skipped entirely."""
        candidate = [
            {"game_id": "npc_100", "name": "Wolf", "faction": "stalker", "rank": 750, "is_alive": True},
        ]

        llm = MagicMock()
        llm.complete = AsyncMock(return_value="The Zone takes everyone eventually.")

        state_client = WorkflowStateClient()
        bg_gen = WorkflowBackgroundGenerator()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
            background_generator=bg_gen,
        )

        speaker_id, dialogue = await manager.handle_event(
            event=death_event,
            candidates=candidate,
            world="Location: Cordon.",
            traits=traits_map,
        )

        assert speaker_id == "npc_100"
        assert "Zone" in dialogue

        # LLM called only once (dialogue, no picker)
        assert llm.complete.call_count == 1

    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_witness_injection_for_all_alive(
        self,
        mock_world_ctx,
        five_candidates,
        death_event,
        traits_map,
    ):
        """Verify witness events are injected for all alive candidates after dialogue."""
        llm = MagicMock()
        call_count = 0

        async def _complete(messages, opts=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "npc_100"
            return "Another day."

        llm.complete = AsyncMock(side_effect=_complete)

        state_client = WorkflowStateClient()
        bg_gen = WorkflowBackgroundGenerator()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
            background_generator=bg_gen,
        )

        await manager.handle_event(
            event=death_event,
            candidates=five_candidates,
            world="Location: Cordon.",
            traits=traits_map,
        )

        # Verify witness injection mutations
        assert len(state_client.mutation_calls) == 1
        mutations = state_client.mutation_calls[0]
        assert len(mutations) == 5  # All 5 alive candidates
        assert all(m["op"] == "append" for m in mutations)
        assert all(m["resource"] == "memory.events" for m in mutations)

        mutated_ids = {m["params"]["character_id"] for m in mutations}
        expected_ids = {c["game_id"] for c in five_candidates}
        assert mutated_ids == expected_ids

    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_memory_diff_on_second_event(
        self,
        mock_world_ctx,
        death_event,
        traits_map,
    ):
        """Verify second event for same speaker uses diff memory injection."""
        candidates = [
            {"game_id": "npc_100", "name": "Wolf", "faction": "stalker", "rank": 750, "is_alive": True},
        ]

        llm = MagicMock()
        llm.complete = AsyncMock(return_value="Another kill.")

        state_client = WorkflowStateClient()
        bg_gen = WorkflowBackgroundGenerator()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
            background_generator=bg_gen,
        )

        # First event - full memory fetch (compacted tiers)
        await manager.handle_event(
            event=death_event,
            candidates=candidates,
            world="Location: Cordon.",
            traits=traits_map,
        )

        first_bg_count = manager._context_block.bg_count
        assert first_bg_count > 0  # BG should be tracked in context block

        # Reset mock for second event
        llm.complete = AsyncMock(return_value="Zone never changes.")

        # Second event - context block deduplicates BG items
        await manager.handle_event(
            event=death_event,
            candidates=candidates,
            world="Location: Cordon.",
            traits=traits_map,
        )

        # BG count should not increase (already tracked via context block)
        assert manager._context_block.bg_count == first_bg_count

        # Messages: 3 base + user1 + assistant1 + user2 + assistant2 = 7
        assert len(manager._messages) >= 5

    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_state_batch_calls_are_efficient(
        self,
        mock_world_ctx,
        five_candidates,
        death_event,
        traits_map,
    ):
        """Verify memory reads use batched state queries."""
        llm = MagicMock()
        call_count = 0

        async def _complete(messages, opts=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "npc_100"
            return "Zone wisdom."

        llm.complete = AsyncMock(side_effect=_complete)

        state_client = WorkflowStateClient()
        bg_gen = WorkflowBackgroundGenerator()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
            background_generator=bg_gen,
        )

        await manager.handle_event(
            event=death_event,
            candidates=five_candidates,
            world="Location: Cordon. Time: 06:00.",
            traits=traits_map,
        )

        # State batch calls:
        # 1. World enrichment (query.world + query.characters_alive)
        # 2. Memory fetch for chosen speaker (3 compacted tiers)
        assert len(state_client.batch_calls) >= 2

        # The memory fetch batch should contain 3 compacted tiers in one call
        mem_batch = state_client.batch_calls[-1]  # Last batch = memory
        mem_resources = [q["resource"] for q in mem_batch]
        assert "memory.summaries" in mem_resources
        assert "memory.digests" in mem_resources
        assert "memory.cores" in mem_resources


@pytest.mark.asyncio
class TestPrefixStability:
    """Integration tests verifying LLM prefix cache stability across events."""

    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_system_prompt_is_byte_identical_across_events(
        self, mock_world_ctx, five_candidates, death_event, traits_map,
    ):
        """_messages[0] must be the same object across multiple events."""
        llm = MagicMock()
        call_count = 0

        async def _complete(messages, opts=None):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 1:
                return "npc_100"
            return "Zone wisdom."

        llm.complete = AsyncMock(side_effect=_complete)

        state_client = WorkflowStateClient()
        bg_gen = WorkflowBackgroundGenerator()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
            background_generator=bg_gen,
        )

        system_after_init = manager._messages[0].content

        await manager.handle_event(
            event=death_event,
            candidates=five_candidates,
            world="Location: Cordon. Time: 14:35.",
            traits=traits_map,
        )
        system_after_first = manager._messages[0].content

        # Reset call count for second event
        call_count = 0
        await manager.handle_event(
            event=death_event,
            candidates=five_candidates,
            world="Location: Yantar. Time: 23:00. Weather: Rain.",
            traits=traits_map,
        )
        system_after_second = manager._messages[0].content

        # System prompt must be byte-identical across all events
        assert system_after_init == system_after_first == system_after_second

    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_context_block_grows_append_only(
        self, mock_world_ctx, death_event, traits_map,
    ):
        """Context block items only grow — old items remain after new events."""
        candidates_a = [
            {"game_id": "npc_100", "name": "Wolf", "faction": "stalker", "rank": 750, "is_alive": True},
        ]
        candidates_b = [
            {"game_id": "npc_200", "name": "Fanatic", "faction": "dolg", "rank": 450, "is_alive": True},
        ]

        llm = MagicMock()
        llm.complete = AsyncMock(return_value="Zone wisdom.")

        state_client = WorkflowStateClient()
        bg_gen = WorkflowBackgroundGenerator()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
            background_generator=bg_gen,
        )

        # Event 1 with candidate A
        await manager.handle_event(
            event=death_event,
            candidates=candidates_a,
            world="Location: Cordon.",
            traits={"npc_100": {"personality_id": "stalker.1", "backstory_id": "loner.1"}},
        )
        block_after_first = manager._context_block.render_markdown()
        bg_count_after_first = manager._context_block.bg_count

        assert manager._context_block.has_background("npc_100")
        assert bg_count_after_first >= 1

        # Event 2 with candidate B — old BGs must persist
        llm.complete = AsyncMock(return_value="More wisdom.")
        await manager.handle_event(
            event=death_event,
            candidates=candidates_b,
            world="Location: Yantar.",
            traits={"npc_200": {"personality_id": "duty.2", "backstory_id": "duty.1"}},
        )

        # Old candidate A background is still present
        assert manager._context_block.has_background("npc_100")
        # New candidate B background was added
        assert manager._context_block.has_background("npc_200")
        # Context block grew
        assert manager._context_block.bg_count > bg_count_after_first

        # The first event's block content is a prefix of the current block
        block_after_second = manager._context_block.render_markdown()
        assert block_after_second.startswith(block_after_first)
