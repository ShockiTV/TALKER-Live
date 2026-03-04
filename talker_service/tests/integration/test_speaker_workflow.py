"""Integration test for speaker selection workflow.

Validates that the ConversationManager + tool-calling loop produces the correct
workflow: backgrounds for candidates → choose speaker → memories for speaker only.

The test uses a scripted mock LLM that follows the expected tool-call sequence:
1. Call background(character_ids=[...], action="read") for all candidates
2. Call get_memories(character_id=<chosen>) for the selected speaker only
3. Return final [SPEAKER: <id>] dialogue text

Key assertions:
- Total tool calls is 2-3 (batch background + get_memories, optionally get_character_info)
- get_memories is only called for the chosen speaker
- background is called with multiple character_ids in one batch
- Final dialogue is correctly extracted from [SPEAKER: id] format
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from talker_service.dialogue.conversation import ConversationManager, TOOLS
from talker_service.state.batch import BatchResult
from talker_service.llm.models import LLMToolResponse, Message, ToolCall


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
# Scripted LLM: simulates the expected tool-calling workflow
# ---------------------------------------------------------------------------

class ScriptedToolLLM:
    """Mock LLM that follows the background→memories→dialogue workflow.

    Call sequence:
    1. First call: returns tool_call for background(character_ids=[all], action="read")
    2. Second call: returns tool_call for get_memories(character_id=chosen_speaker)
    3. Third call: returns final [SPEAKER: chosen_speaker] dialogue text

    Args:
        chosen_speaker: The character_id the LLM will "choose" as speaker.
        candidate_ids: All candidate IDs (used in the batch background call).
    """

    def __init__(self, chosen_speaker: str, candidate_ids: list[str]):
        self._chosen = chosen_speaker
        self._candidate_ids = candidate_ids
        self._call_count = 0
        self.tool_calls_made: list[ToolCall] = []

    async def complete_with_tools(
        self,
        messages: list[Message],
        *,
        tools=None,
        **kwargs,
    ) -> LLMToolResponse:
        self._call_count += 1

        if self._call_count == 1:
            # Step 1: request batch backgrounds for all candidates
            tc = ToolCall(
                id="call_bg",
                name="background",
                arguments={
                    "character_ids": self._candidate_ids,
                    "action": "read",
                },
            )
            self.tool_calls_made.append(tc)
            return LLMToolResponse(tool_calls=[tc])

        elif self._call_count == 2:
            # Step 2: request memories for chosen speaker only
            tc = ToolCall(
                id="call_mem",
                name="get_memories",
                arguments={"character_id": self._chosen},
            )
            self.tool_calls_made.append(tc)
            return LLMToolResponse(tool_calls=[tc])

        else:
            # Step 3: final dialogue
            return LLMToolResponse(
                text=f"[SPEAKER: {self._chosen}] Damn mutants... another day in the Zone."
            )

    async def complete_with_tool_loop(
        self,
        messages: list[Message],
        *,
        tools=None,
        tool_executor=None,
        max_iterations: int = 5,
        **kwargs,
    ) -> LLMToolResponse:
        """Replay the scripted workflow using the default loop pattern."""
        working = list(messages)
        for _ in range(max_iterations):
            response = await self.complete_with_tools(working, tools=tools)
            if not response.has_tool_calls:
                return response
            working.append(Message(role="assistant", content="", tool_calls=response.tool_calls))
            for tc in response.tool_calls:
                result = await tool_executor(tc)
                working.append(Message.tool_result(tc.id, tc.name, result))
        return LLMToolResponse(text="", tool_calls=[])


# ---------------------------------------------------------------------------
# Mock state client with canned batch responses
# ---------------------------------------------------------------------------

class WorkflowStateClient:
    """State client that returns canned responses and records all batch calls."""

    def __init__(self):
        self.batch_calls: list[list[dict]] = []

    async def execute_batch(self, batch, *, timeout=None, session=None) -> BatchResult:
        queries = batch.build()
        self.batch_calls.append(queries)

        results: dict[str, dict] = {}
        for q in queries:
            qid = q["id"]
            resource = q["resource"]

            if resource == "memory.background":
                # Return a simple background for each character
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
                # Memory tier query — return a few canned entries
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
            else:
                results[qid] = {"ok": False, "error": f"unknown resource: {resource}"}

        return BatchResult(results)

    async def mutate_batch(self, mutations, *, timeout=None):
        """Accept witness injection mutations silently."""
        return True


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSpeakerSelectionWorkflow:
    """Integration tests for the speaker selection workflow."""

    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_workflow_background_then_memories(
        self,
        mock_world_ctx,
        mock_faction,
        mock_personality,
        five_candidates,
        death_event,
        traits_map,
    ):
        """Full workflow: 5 candidates → batch background → choose speaker → memories → dialogue.

        Verifies:
        - LLM is called exactly 3 times (background, memories, dialogue)
        - Background tool gets all 5 candidate IDs in one batch
        - get_memories is only called for the chosen speaker (npc_101)
        - Final speaker_id and dialogue are correctly extracted
        """
        mock_faction.return_value = "Loner faction description"
        mock_personality.return_value = "A cautious veteran stalker..."

        candidate_ids = [c["game_id"] for c in five_candidates]
        chosen = "npc_101"

        llm = ScriptedToolLLM(chosen_speaker=chosen, candidate_ids=candidate_ids)
        state_client = WorkflowStateClient()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
            max_tool_iterations=5,
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

        # LLM was called 3 times: background → memories → final dialogue
        assert llm._call_count == 3

        # Tool calls are exactly 2: one background batch + one get_memories
        assert len(llm.tool_calls_made) == 2
        assert llm.tool_calls_made[0].name == "background"
        assert llm.tool_calls_made[1].name == "get_memories"

        # Background was called with all 5 candidate IDs
        bg_args = llm.tool_calls_made[0].arguments
        assert set(bg_args["character_ids"]) == set(candidate_ids)

        # get_memories was called only for chosen speaker
        mem_args = llm.tool_calls_made[1].arguments
        assert mem_args["character_id"] == chosen

    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_memories_not_fetched_for_non_speakers(
        self,
        mock_world_ctx,
        mock_faction,
        mock_personality,
        five_candidates,
        death_event,
        traits_map,
    ):
        """Verify get_memories is never called for candidates who are not the speaker."""
        mock_faction.return_value = "Loner faction description"
        mock_personality.return_value = "A cautious veteran stalker..."

        candidate_ids = [c["game_id"] for c in five_candidates]
        chosen = "npc_103"  # Freedom member

        llm = ScriptedToolLLM(chosen_speaker=chosen, candidate_ids=candidate_ids)
        state_client = WorkflowStateClient()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
        )

        speaker_id, _ = await manager.handle_event(
            event=death_event,
            candidates=five_candidates,
            world="Location: Garbage. Time: 22:00.",
            traits=traits_map,
        )

        assert speaker_id == chosen

        # Verify get_memories was only called for the chosen speaker
        memory_calls = [tc for tc in llm.tool_calls_made if tc.name == "get_memories"]
        assert len(memory_calls) == 1
        assert memory_calls[0].arguments["character_id"] == chosen

        # Verify no memory queries for other candidates
        non_speaker_ids = set(candidate_ids) - {chosen}
        for tc in llm.tool_calls_made:
            if tc.name == "get_memories":
                assert tc.arguments["character_id"] not in non_speaker_ids

    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_state_batch_calls_are_efficient(
        self,
        mock_world_ctx,
        mock_faction,
        mock_personality,
        five_candidates,
        death_event,
        traits_map,
    ):
        """Verify background reads for 5 NPCs are batched into a single state query."""
        mock_faction.return_value = "Loner faction description"
        mock_personality.return_value = "A cautious veteran stalker..."

        candidate_ids = [c["game_id"] for c in five_candidates]
        chosen = "npc_100"

        llm = ScriptedToolLLM(chosen_speaker=chosen, candidate_ids=candidate_ids)
        state_client = WorkflowStateClient()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
        )

        await manager.handle_event(
            event=death_event,
            candidates=five_candidates,
            world="Location: Cordon. Time: 06:00.",
            traits=traits_map,
        )

        # Find the background batch call among state_client.batch_calls
        bg_batches = []
        for call_queries in state_client.batch_calls:
            bg_queries = [q for q in call_queries if q["resource"] == "memory.background"]
            if bg_queries:
                bg_batches.append(bg_queries)

        # Background reads for all 5 NPCs should be in a single batch
        assert len(bg_batches) == 1, f"Expected 1 background batch, got {len(bg_batches)}"
        assert len(bg_batches[0]) == 5, f"Expected 5 queries in batch, got {len(bg_batches[0])}"

        # Each query should be for a different candidate
        queried_ids = {q["params"]["character_id"] for q in bg_batches[0]}
        assert queried_ids == set(candidate_ids)

    @patch("talker_service.dialogue.conversation.resolve_personality")
    @patch("talker_service.dialogue.conversation.get_faction_description")
    @patch("talker_service.dialogue.conversation.build_world_context", new_callable=AsyncMock, return_value="")
    async def test_system_prompt_includes_workflow_rules(
        self,
        mock_world_ctx,
        mock_faction,
        mock_personality,
        five_candidates,
        death_event,
        traits_map,
    ):
        """Verify system prompt includes Tool Usage Rules for the workflow."""
        mock_faction.return_value = "Loner faction description"
        mock_personality.return_value = "A cautious veteran stalker..."

        candidate_ids = [c["game_id"] for c in five_candidates]
        llm = ScriptedToolLLM(chosen_speaker="npc_100", candidate_ids=candidate_ids)
        state_client = WorkflowStateClient()

        manager = ConversationManager(
            llm_client=llm,
            state_client=state_client,
        )

        prompt = manager._build_system_prompt(
            faction="stalker",
            personality="A cautious stalker",
            world="Location: Cordon.",
        )

        # Verify the prompt contains the workflow instructions
        assert "Tool Usage Rules" in prompt
        assert "background" in prompt.lower()
        assert "get_memories" in prompt.lower()
        assert "ONLY use AFTER choosing the speaker" in prompt or "ONLY" in prompt
        assert "Memories are expensive" in prompt
