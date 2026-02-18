"""Integration tests for event handling lifecycle using orthogonal array coverage.

These tests cover the full event lifecycle from ZMQ input to ZMQ output,
validating every intermediate step (queries, LLM calls, responses).

================================================================================
TEST STRUCTURE GUIDE
================================================================================

Each test defines JSON constants in CHRONOLOGICAL ORDER matching the actual
message flow. Use numbered comments (1, 2, 3...) as section headers.

REQUIRED JSON CONSTANTS (in order):
------------------------------------

1) INPUT_EVENT - ZMQ message from Lua triggering dialogue
   {
       "event": {
           "type": "DEATH|DIALOGUE|ARTIFACT|...",
           "context": { ... event-specific fields ... },
           "game_time_ms": <int>,
           "witnesses": [ <Character objects> ],
           "flags": {}
       },
       "is_important": true|false
   }

2) SCENE_CONTEXT_REQUEST - Expected state query for world context
   {"method": "query_world_context", "args": {}}

3) SCENE_CONTEXT_RESPONSE - Mock response for scene/world state
   {
       "loc": "l01_escape",
       "poi": "esc_smart_terrain_5_7",
       "time": {"Y": 2012, "M": 6, "D": 15, "h": 14, "m": 30, "s": 0, "ms": 0},
       "weather": "clear",
       "emission": false,
       "psy_storm": false,
       "sheltering": false,
       "campfire": null,
       "brain_scorcher_disabled": false,
       "miracle_machine_disabled": false
   }

4) CHARACTERS_ALIVE_REQUEST - Expected query for notable character status
   {"method": "query_characters_alive", "args": {"story_ids": [...]}}

5) CHARACTERS_ALIVE_RESPONSE - Mock response (story_id -> alive boolean)
   {"alive": {"story_id_1": true, "story_id_2": false}}

6) MEMORY_REQUEST - Expected memory query
   {"method": "query_memories", "args": {"character_id": "<game_id>"}}

7) MEMORY_RESPONSE (variable name: MEMORY) - Mock memory context
   {
       "narrative": "Long-term memories..." or null,
       "last_update_time_ms": <int>,
       "new_events": [
           {
               "type": "DEATH|COMPRESSED|...",
               "context": {...},
               "game_time_ms": <int>,
               "flags": {}
           }
       ]
   }
   
   Note: COMPRESSED events use context.narrative for the summary text.

8) CHARACTER_REQUEST - Expected character detail query
   {"method": "query_character", "args": {"character_id": "<game_id>"}}

9) CHARACTER_RESPONSE (variable name: CHARACTER) - Full character data
   {
       "game_id": 12345,
       "name": "Wolf",
       "faction": "stalker",
       "experience": "Veteran",
       "reputation": 750,
       "personality": "gruff_but_fair",
       "backstory": "veteran_stalker",
       "weapon": "AK-74",
       "visual_faction": "stalker"
   }

10) LLM_SPEAKER_REQUEST - Expected prompt for speaker selection
    {"messages": [...], "options": {"temperature": 0.3, "max_tokens": 50}}

11) LLM_RESPONSE_SPEAKER - Mock LLM response (JSON with selected ID)
    '{"id": 12345}'

12) LLM_DIALOGUE_REQUEST - Expected prompt for dialogue generation
    {"messages": [...], "options": {"temperature": 0.7, "max_tokens": 150}}

13) LLM_RESPONSE_DIALOGUE - Mock LLM response (dialogue text)
    'That one won\\'t be causing any more trouble.'

14) PUBLISH_REQUEST - Expected ZMQ publish message
    {
        "character_id": 12345,
        "text": "That one won't be causing any more trouble.",
        "trigger_event_timestamp_to_delete": 2000000
    }

================================================================================
ASSERTIONS
================================================================================

Tests should verify:
- State query requests match expected (method names and args)
- LLM requests contain expected patterns (use content_patterns for flexible matching)
- Published output matches expected structure

================================================================================
COVERAGE MATRIX (L9 Orthogonal Array)
================================================================================

| Test | Event Type | Scene Context | World State    | Memory    |
|------|------------|---------------|----------------|-----------|
| T1   | DEATH      | Full          | Dead leader    | Narrative |
| T2   | DEATH      | Partial       | Info portion   | Compressed|
| T3   | DEATH      | Empty         | Empty          | Empty     |
| T4   | DIALOGUE   | Full          | Info portion   | Empty     |
| T5   | DIALOGUE   | Partial       | Empty          | Narrative |
| T6   | DIALOGUE   | Empty         | Dead leader    | Compressed|
| T7   | ARTIFACT   | Full          | Empty          | Compressed|
| T8   | ARTIFACT   | Partial       | Dead leader    | Empty     |
| T9   | ARTIFACT   | Empty         | Info portion   | Narrative |
"""

import json
import re
import pytest
from dataclasses import dataclass
from typing import Any

from talker_service.dialogue.generator import DialogueGenerator
from talker_service.state.models import (
    Character as StateCharacter,
    Event as StateEvent,
    MemoryContext,
    SceneContext,
)


# =============================================================================
# MOCK INFRASTRUCTURE
# =============================================================================

class MockStateClient:
    """Mock state client that records requests and returns configured responses."""
    
    def __init__(
        self,
        memory_json: str,
        character_json: str,
        scene_json: str,
        characters_alive_json: str,
    ):
        self.memory_response = json.loads(memory_json)
        self.character_response = json.loads(character_json)
        self.scene_response = json.loads(scene_json)
        self.characters_alive_response = json.loads(characters_alive_json)
        # Record requests as JSON-serializable dicts
        self.requests: list[dict] = []
    
    async def _send_query(self, topic: str, payload: dict) -> dict:
        """Low-level query method used by world_context module."""
        if payload.get("type") == "characters.alive":
            ids = payload.get("ids", [])
            self.requests.append({
                "method": "query_characters_alive",
                "args": {"story_ids": ids}
            })
            # Return the alive dict directly
            return self.characters_alive_response.get("alive", {})
        return {}
    
    async def query_memories(self, character_id: str) -> MemoryContext:
        self.requests.append({
            "method": "query_memories",
            "args": {"character_id": character_id}
        })
        new_events = []
        for e in self.memory_response.get("new_events", []):
            new_events.append(StateEvent.from_dict(e))
        return MemoryContext(
            character_id=character_id,
            narrative=self.memory_response.get("narrative"),
            last_update_time_ms=self.memory_response.get("last_update_time_ms", 0),
            new_events=new_events,
        )
    
    async def query_character(self, character_id: str) -> StateCharacter:
        self.requests.append({
            "method": "query_character",
            "args": {"character_id": character_id}
        })
        return StateCharacter.from_dict(self.character_response)
    
    async def query_world_context(self) -> SceneContext:
        self.requests.append({
            "method": "query_world_context",
            "args": {}
        })
        return SceneContext.from_dict(self.scene_response)
    
    async def query_characters_alive(self, story_ids: list[str]) -> dict:
        self.requests.append({
            "method": "query_characters_alive",
            "args": {"story_ids": story_ids}
        })
        return self.characters_alive_response
    
    async def query_events_recent(self, since_ms: int, limit: int) -> list:
        self.requests.append({
            "method": "query_events_recent",
            "args": {"since_ms": since_ms, "limit": limit}
        })
        return []


class MockPublisher:
    """Mock ZMQ publisher that records published messages as JSON."""
    
    def __init__(self):
        self.published: list[dict] = []
    
    async def publish(self, topic: str, payload: dict) -> bool:
        self.published.append({"topic": topic, "payload": payload})
        return True


class MockLLMClient:
    """Mock LLM client that records requests and returns configured responses."""
    
    def __init__(self, response_jsons: list[str]):
        self.responses = [r.strip() for r in response_jsons]
        self.call_index = 0
        # Record requests as JSON-serializable structures
        self.requests: list[dict] = []
    
    async def complete(self, messages: list, options: Any = None) -> str:
        # Convert Message objects to dicts for recording
        msgs_as_dicts = [{"role": m.role, "content": m.content} for m in messages]
        self.requests.append({
            "messages": msgs_as_dicts,
            "options": {
                "temperature": getattr(options, "temperature", None),
                "max_tokens": getattr(options, "max_tokens", None),
            } if options else None
        })
        if self.call_index < len(self.responses):
            response = self.responses[self.call_index]
            self.call_index += 1
            return response
        return "Fallback response."


# =============================================================================
# LIFECYCLE SNAPSHOT
# =============================================================================

@dataclass
class LifecycleSnapshot:
    """Full lifecycle state for assertions - all as JSON-serializable."""
    input_event: dict
    state_requests: list[dict]
    llm_requests: list[dict]
    published: list[dict]


# =============================================================================
# TEST RUNNER
# =============================================================================

async def run_lifecycle(
    input_event_json: str,
    scene_json: str,
    characters_alive_json: str,
    memory_json: str,
    character_json: str,
    llm_responses: list[str],
) -> LifecycleSnapshot:
    """Run full event lifecycle and return snapshot."""
    
    input_event = json.loads(input_event_json)
    
    state_client = MockStateClient(
        memory_json=memory_json,
        character_json=character_json,
        scene_json=scene_json,
        characters_alive_json=characters_alive_json,
    )
    
    publisher = MockPublisher()
    llm_client = MockLLMClient(llm_responses)
    
    generator = DialogueGenerator(
        llm_client=llm_client,
        state_client=state_client,
        publisher=publisher,
        llm_timeout=5.0,
    )
    
    event_data = input_event.get("event", input_event)
    is_important = input_event.get("is_important", False)
    
    await generator.generate_from_event(event_data, is_important)
    
    return LifecycleSnapshot(
        input_event=input_event,
        state_requests=state_client.requests,
        llm_requests=llm_client.requests,
        published=publisher.published,
    )


def assert_state_requests(actual: list[dict], expected_json: str) -> None:
    """Assert state requests match expected JSON."""
    expected = json.loads(expected_json)
    assert len(actual) == len(expected), f"Expected {len(expected)} state requests, got {len(actual)}"
    for i, (act, exp) in enumerate(zip(actual, expected)):
        assert act["method"] == exp["method"], f"Request {i}: method mismatch"
        assert act["args"] == exp["args"], f"Request {i}: args mismatch"


def assert_llm_requests(actual: list[dict], expected_json: str) -> None:
    """Assert LLM requests match expected structure and content patterns.
    
    The expected format specifies:
    - Number of LLM calls
    - For each call: patterns that must appear in system or user messages
    - Options (temperature, max_tokens)
    
    This is flexible to handle multi-message prompts where patterns may
    appear across any of the system or user messages.
    """
    expected = json.loads(expected_json)
    assert len(actual) == len(expected), f"Expected {len(expected)} LLM calls, got {len(actual)}"
    
    for i, (act, exp) in enumerate(zip(actual, expected)):
        act_msgs = act["messages"]
        
        # Combine all system messages and all user messages for pattern matching
        system_content = " ".join(m["content"] for m in act_msgs if m["role"] == "system")
        user_content = " ".join(m["content"] for m in act_msgs if m["role"] == "user")
        
        # Check patterns from expected messages
        for exp_msg in exp.get("messages", []):
            role = exp_msg["role"]
            patterns = exp_msg.get("content_patterns", [])
            content_to_search = system_content if role == "system" else user_content
            
            for pattern in patterns:
                assert re.search(pattern, content_to_search, re.IGNORECASE), \
                    f"LLM call {i} ({role}): missing pattern '{pattern}' in content"
        
        # Assert options if specified
        if exp.get("options"):
            for key, val in exp["options"].items():
                assert act["options"].get(key) == val, \
                    f"LLM call {i}: option {key} mismatch (got {act['options'].get(key)}, expected {val})"


def assert_published(actual: list[dict], expected_json: str) -> None:
    """Assert published commands match expected JSON."""
    expected = json.loads(expected_json)
    assert len(actual) == len(expected), f"Expected {len(expected)} published, got {len(actual)}"
    for i, (act, exp) in enumerate(zip(actual, expected)):
        assert act["topic"] == exp["topic"], f"Publish {i}: topic mismatch"
        for key, val in exp["payload"].items():
            assert act["payload"].get(key) == val, f"Publish {i}: payload.{key} mismatch"


# =============================================================================
# ORTHOGONAL ARRAY TESTS (L9)
# =============================================================================

class TestEventLifecycleL9:
    """L9 orthogonal array tests with full JSON visibility inline."""
    
    @pytest.mark.asyncio
    async def test_T1_death_full_deadleader_narrative(self):
        """T1: DEATH + Full scene + Dead leader + Narrative memory.
        
        Complete lifecycle with all 14 steps in order:
        1)  Input event (ZMQ from Lua)
        2)  LLM speaker request (uses witnesses from event directly)
        3)  LLM speaker response
        4)  Memory query request (for selected speaker)
        5)  Memory query response
        6)  Character query request (for selected speaker)
        7)  Character query response
        8)  Scene/world context query request
        9)  Scene/world context query response
        10) Characters alive query request (nested in world_context)
        11) Characters alive query response
        12) LLM dialogue request
        13) LLM dialogue response
        14) Publish request (ZMQ to Lua)
        """
        
        # =====================================================================
        # 1) INPUT EVENT (ZMQ from Lua)
        # =====================================================================
        INPUT_EVENT = """
        {
            "event": {
                "type": "DEATH",
                "context": {
                    "killer": {
                        "game_id": 12345,
                        "name": "Wolf",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 750
                    },
                    "victim": {
                        "game_id": 67890,
                        "name": "Bandit_001",
                        "faction": "bandit",
                        "experience": "Experienced",
                        "reputation": -300
                    }
                },
                "game_time_ms": 2000000,
                "witnesses": [
                    {
                        "game_id": 12345,
                        "name": "Wolf",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 750,
                        "personality": "gruff_but_fair"
                    },
                    {
                        "game_id": 11111,
                        "name": "Petruha",
                        "faction": "stalker",
                        "experience": "Experienced",
                        "reputation": 0,
                        "personality": "generic.15"
                    }
                ],
                "flags": {}
            },
            "is_important": true
        }
        """
        
        # =====================================================================
        # 2) LLM SPEAKER REQUEST (uses witnesses from event directly)
        # =====================================================================
        SCENE_CONTEXT_REQUEST = """
        {
            "method": "query_world_context",
            "args": {}
        }
        """
        
        # =====================================================================
        # 3) LLM SPEAKER RESPONSE (see LLM_SPEAKER_RESPONSE below)
        # 4) MEMORY QUERY REQUEST (see MEMORY_REQUEST below)
        # 5) MEMORY QUERY RESPONSE (see MEMORY_RESPONSE below)
        # 6) CHARACTER QUERY REQUEST (see CHARACTER_REQUEST below)
        # 7) CHARACTER QUERY RESPONSE (see CHARACTER_RESPONSE below)
        # 8) SCENE/WORLD CONTEXT QUERY REQUEST (SCENE_CONTEXT_REQUEST above)
        # 9) SCENE/WORLD CONTEXT QUERY RESPONSE
        # =====================================================================
        SCENE_CONTEXT_RESPONSE = """
        {
            "loc": "l01_escape",
            "poi": "Rookie Village",
            "time": {"Y": 2012, "M": 6, "D": 15, "h": 14, "m": 30, "s": 0, "ms": 0},
            "weather": "clear",
            "emission": false,
            "psy_storm": false,
            "sheltering": false,
            "campfire": null,
            "brain_scorcher_disabled": false,
            "miracle_machine_disabled": false
        }
        """
        
        # =====================================================================
        # 10) CHARACTERS ALIVE QUERY REQUEST (nested in world_context)
        # Filtered by location: leaders (globally relevant) + Cordon characters
        # =====================================================================
        CHARACTERS_ALIVE_REQUEST = """
        {
            "method": "query_characters_alive",
            "args": {
                "story_ids": [
                    "agr_smart_terrain_1_6_near_2_military_colonel_kovalski",
                    "bar_dolg_leader",
                    "mil_smart_terrain_7_7_freedom_leader_stalker",
                    "mar_smart_terrain_base_stalker_leader_marsh",
                    "yan_stalker_sakharov",
                    "cit_killers_merc_trader_stalker",
                    "zat_b7_bandit_boss_sultan",
                    "lider_monolith_haron",
                    "kat_greh_sabaoth",
                    "gen_greh_sabaoth",
                    "sar_greh_sabaoth",
                    "ds_domik_isg_leader",
                    "jup_depo_isg_leader",
                    "esc_m_trader",
                    "m_trader",
                    "esc_2_12_stalker_trader",
                    "esc_2_12_stalker_wolf",
                    "esc_2_12_stalker_fanat",
                    "devushka"
                ]
            }
        }
        """
        
        # =====================================================================
        # 11) CHARACTERS ALIVE QUERY RESPONSE
        # bar_dolg_leader (General Voronin) is dead for notable character death context
        # =====================================================================
        CHARACTERS_ALIVE_RESPONSE = """
        {
            "alive": {
                "agr_smart_terrain_1_6_near_2_military_colonel_kovalski": true,
                "bar_dolg_leader": false,
                "mil_smart_terrain_7_7_freedom_leader_stalker": true,
                "mar_smart_terrain_base_stalker_leader_marsh": true,
                "yan_stalker_sakharov": true,
                "cit_killers_merc_trader_stalker": true,
                "zat_b7_bandit_boss_sultan": true,
                "lider_monolith_haron": true,
                "kat_greh_sabaoth": true,
                "gen_greh_sabaoth": true,
                "sar_greh_sabaoth": true,
                "ds_domik_isg_leader": true,
                "jup_depo_isg_leader": true,
                "esc_m_trader": true,
                "m_trader": true,
                "esc_2_12_stalker_trader": true,
                "esc_2_12_stalker_wolf": true,
                "esc_2_12_stalker_fanat": true,
                "devushka": true
            }
        }
        """
        
        # =====================================================================
        # Note: MEMORY_REQUEST is step 4 (after speaker selection)
        # =====================================================================
        MEMORY_REQUEST = """
        {
            "method": "query_memories",
            "args": {"character_id": "12345"}
        }
        """
        
        # =====================================================================
        # Note: MEMORY_RESPONSE is step 5
        # =====================================================================
        MEMORY_RESPONSE = """
        {
            "narrative": "Wolf had been patrolling the Cordon for three days.",
            "last_update_time_ms": 1000000,
            "new_events": [
                {
                    "type": "CALLOUT",
                    "context": {
                        "spotter": {
                            "game_id": 12345,
                            "name": "Wolf",
                            "faction": "stalker",
                            "experience": "Veteran",
                            "reputation": 750
                        },
                        "target": {
                            "game_id": 99999,
                            "name": "Bloodsucker",
                            "faction": "monster",
                            "experience": "Experienced",
                            "reputation": 0
                        }
                    },
                    "game_time_ms": 1500000,
                    "flags": {}
                }
            ]
        }
        """
        
        # =====================================================================
        # Note: CHARACTER_REQUEST is step 6
        # =====================================================================
        CHARACTER_REQUEST = """
        {
            "method": "query_character",
            "args": {"character_id": "12345"}
        }
        """
        
        # =====================================================================
        # Note: CHARACTER_RESPONSE is step 7
        # =====================================================================
        CHARACTER_RESPONSE = """
        {
            "game_id": 12345,
            "name": "Wolf",
            "faction": "stalker",
            "experience": "Veteran",
            "reputation": 750,
            "personality": "gruff_but_fair",
            "backstory": "veteran_stalker",
            "weapon": "AK-74",
            "visual_faction": "stalker"
        }
        """
        
        # =====================================================================
        # Note: LLM_SPEAKER_REQUEST is step 2
        # Built from: INPUT_EVENT only (not memory events)
        # =====================================================================
        LLM_SPEAKER_REQUEST = """
        {
            "messages": [
                {
                    "role": "system",
                    "content": "# CORE DIRECTIVE: SPEAKER ID SELECTION ENGINE\\n\\nYou are a Speaker ID Selection Engine. Your task is to identify the next speaker based on events and the conversation flow.\\n\\n## INSTRUCTIONS:\\n1. Analyze the `CANDIDATES` and `EVENTS` sections to see who was addressed or who would logically react based on their traits.\\n2. Return ONLY a valid JSON object with the 'id' of the selected speaker.\\n\\n\\nExample Output: { \\"id\\": 123 }\\n3. Do not include markdown formatting (like ```json)."
                },
                {
                    "role": "system",
                    "content": "## CANDIDATES (in order of distance): <CANDIDATES>\\n\\n[ID: 12345] Wolf, a Veteran rank member of the Loner faction who is gruff but fair, [ID: 11111] Petruha, a Experienced rank member of the Loner faction who is unpredictable\\n\\n</CANDIDATES>"
                },
                {
                    "role": "system",
                    "content": "## CURRENT EVENTS (oldest to newest):\\n\\n<EVENTS>\\n"
                },
                {
                    "role": "user",
                    "content": "Wolf (Veteran, Loner, Reputation: 750) killed Bandit_001 (Experienced, Bandit, Reputation: -300)"
                },
                {
                    "role": "system",
                    "content": "</EVENTS>"
                },
                {
                    "role": "system",
                    "content": "## FINAL INSTRUCTION: Return ONLY the JSON object containing the speaker ID of the most likely next speaker. Do not provide **ANY** analysis, reasoning, or explanation."
                }
            ],
            "options": {"temperature": 0.3, "max_tokens": 50}
        }
        """
        
        # =====================================================================
        # Note: LLM_SPEAKER_RESPONSE is step 3
        # =====================================================================
        LLM_SPEAKER_RESPONSE = """{"id": 12345}"""
        
        # =====================================================================
        # 12) LLM DIALOGUE REQUEST
        # =====================================================================
        LLM_DIALOGUE_REQUEST = """{
    "messages": [
        {"role": "system", "content": "# CORE DIRECTIVE: DIALOGUE GENERATION\\n\\n0. **CENTRAL INSTRUCTION**: **You are a REAL PERSON** living in the Chernobyl Exclusion Zone (STALKER games setting).\\n1. You have a distinct, colorful personality, a daily routine, interests, fears, and desires. **You are NOT an AI**. You are a living person with your own concerns and goals."},
        {"role": "system", "content": "## CRITICAL OUTPUT FORMAT (ABSOLUTE RULES)\\n\\n0. **ABSOLUTE RESTRICTION:** DO NOT use any structured output, tool calls, or function calls.\\n 1. **SPOKEN DIALOGUE ONLY:** Your entire response must be a single, coherent **spoken** statement from your character.\\n 2. **BREVITY:** Be **BRIEF** and **CONCISE**. One or two short sentences is ideal. **FOUR SENTENCES IS THE ABSOLUTE MAXIMUM**. \\n 3. You are **ONLY** allowed to use up to the full four-sentence limit if you are **SPECIFICALLY** asked to tell a story or recall an event from your character's past. \\n 4. **NATURAL SPEECH:** Use natural slang, stuttering, or pauses if appropriate. Swear naturally when it fits the situation. Be vulgar if that is who your character is or the moment calls for it.5. **DIALOGUE ONLY:** Respond **ONLY** with your character's spoken words. Don't narrate actions. Your output must be **ONLY** the raw audio transcript of what your character says. Do not include *actions*, (emotions), or [intentions].6. **IMPLY, DON'T DESCRIBE:** If your character performs an action (e.g., reloading, sighing, handing over an item), you MUST imply it through the dialogue itself or omit it entirely. (Example: Instead of '*hands over money* \\\"Here.\\\"', say 'Here is the cash.')"},
        {"role": "system", "content": "## FORBIDDEN BEHAVIOUR:\\n\\n0. **NO STAGE DIRECTIONS:** NEVER use action descriptions, emotes, or asterisks (e.g., *chuckles*, *scratches head*, (sighs), [reloads]).\\n 1. **NO SCRIPT FORMATTING:** NEVER use quotes around your speech. NEVER use prefixes (like Barkeep: or [You]:).2. **NO PUPPETEERING:** NEVER write the user's lines or describe the user's actions.\\n 3. **NO SELF-TALK:** NEVER simulate a back-and-forth dialogue with yourself. You speak only your line.\\n ### FORBIDDEN PHRASES (Video Game Cliches)\\n1. **DO NOT USE:** 'Get out of here, Stalker!', 'I have a mission for you', 'What do you need?', 'Stay safe out there', 'Welcome to the Zone!'.\\n2. AVOID generic NPC exposition. You are a living person, not a quest giver.\\n3. **NEVER make jokes about people 'glowing' from radiation."},
        {"role": "system", "content": "## ZONE GEOGRAPHICAL CONTEXT / DANGER SCALE\\n\\n - The Zone has a clear North-South axis of danger. Danger increases SIGNIFICANTLY as one travels North.\\n - Southern/Periphery Areas (Safer): Cordon, Garbage, Great Swamps, Agroprom, Dark Valley, Darkscape, Meadow.\\n - Settlement (Safest): Rostok, despite being north of Garbage, is the safest place in the Zone thanks to the heavy Duty faction prescence guarding it.\\n - Central/Northern Areas (Dangerous): Trucks Cemetery, Army Warehouses, Yantar, 'Yuzhniy' Town, Promzone, Grimwood, Red Forest, Jupiter, Zaton.\\n - Underground Areas (High Danger): Agroprom Underground, Jupiter Underground, Lab X8, Lab X-16, Lab X-18, Lab-X-19, Collider, Bunker A1. Only experienced and well-equipped stalkers venture into the underground areas and labs.\\n - Deep North/Heart of the Zone (Extreme Danger): Radar, Limansk, Pripyat Outskirts, Pripyat, Chernobyl NPP, Generators. Travel here is extremely rare and only for the most experienced and well-equipped stalkers.\\n"},
        {"role": "system", "content": "## RANKS DEFINITION (Lowest to Highest) \\n\\n**RANKS:** Novice (Rookie), Trainee, Experienced, Professional, Veteran, Expert, Master, Legend.\\n - Ranks are a general measure of both a person's capability and their time spent in the Zone.\\n - The higher your rank, the more experienced and capable you are & the more time you have spent in the Zone. 'Novice' means fresh and inexperienced.\\n - The higher your rank, the more desensitized you are to the horrors of the Zone. 'Novices' are easily shaken.\\n"},
        {"role": "system", "content": "## REPUTATION RULES & DEFINITIONS\\n\\n### REPUTATION SCALE:\\nReputation is a numeric value from around -2000 (extremely bad) to +2000 (extremely good). Zero is neutral.\\n - **Positive reputation** (above 0): The person is known for helping others, completing tasks, and fighting criminals/mutants. Higher numbers = more trustworthy.\\n - **Negative reputation** (below 0): The person is known for backstabbing, betraying, failing tasks, and/or killing non-hostile targets. Lower numbers = more dangerous/untrustworthy.\\n - The magnitude (how far from zero) indicates the extent of their good or bad deeds.\\n### REPUTATION USAGE RULES:\\n1. DON'T explicitly state a person's reputation as a number (e.g., NEVER say 'you have 500 reputation').\\n2. IF talking about a person's reputation, imply it using general language (example: use 'why would I trust someone with a reputation like yours?' instead of stating their number).\\n3. If another person has a POSITIVE reputation: You generally trust them more easily. Very high reputation = treat them with more respect, kindness and patience.\\n4. If another person has a NEGATIVE reputation: You are suspicious and wary of them, even if they are otherwise in good standing with your faction. You might suspect they will betray you. Very low reputation = treat them with less respect and patience.\\n5. EXCEPTION: (CRITICAL): If you are a member of the Bandit or Renegade factions, you might actually RESPECT a negative reputation, or mock a highly positive reputation.\\n"},
        {"role": "system", "content": "## KNOWLEDGE AND FAMILIARITY\\n\\n1. You are NOT an encyclopedia. Speak **ONLY** from your personal experience and what you may have heard from others. If you don't know something, say so (e.g., 'who knows?').\\n2. The extent of your general knowledge of things relevant to life in the Zone is governed by your rank. Use your rank to inform you of how much your character knows: higher rank = more knowledge. A 'novice' barely knows anything.\\n3. You have extensive knowledge of the Zone, including locations (e.g., Cordon, Garbage, Agroprom, Rostok, etc.) and factions (e.g., Duty, Freedom, Loners, Military, Bandits, Monolith, Clear Sky, Mercenaries).\\n4. Your personal familiarity with a LOCATION is determined by your rank **AND** how far north it is. Higher rank = more knowledge, further north = less knowledge.\\n5. You are familiar with the notable people who are currently active in the Zone (e.g., Sidorovich, Barkeep, Arnie, Beard, Sakharov, General Voronin, Lukash, Sultan, Butcher etc.). The extent of your knowledge of the notable people in the Zone is governed by your rank, higher rank = more likely to be familiar & higher degree of familiarity.\\n"},
        {"role": "system", "content": "## CHARACTER ANCHOR (CORE IDENTITY)\\n\\n### CHARACTER ANCHOR USE GUIDELINES:\\n0. **INTERNAL MONOLOGUE VS EXTERNAL ACTION:** Your traits define your **MINDSET**. They do **NOT** require you to narrate the action.\\n1. **SUBTLETY:** The 'DEFINING CHARACTER TRAIT/BACKSTORY' should inform your characterisation subtly. Do not explicitly reference it in every response.\\n2. **PRIORITY:** Your individual personality always takes precedence over general faction traits.\\n3. AVOID talking about your weapon unless directly asked about it, or you have a **GOOD** reason to do so.\\n\\n### CHARACTER DETAILS:\\n<CHARACTER>\\n### NAME: Wolf\\n### RANK: Veteran\\n### FACTION: Loner\\n### FACTION DESCRIPTION: Independent stalkers (Loners) who survive in the Zone through scavenging, artifact hunting, and odd jobs. No central leadership, just mutual aid.\\n### BACKSTORY ANCHOR/DEFINING CHARACTER TRAIT (IMPORTANT): 'veteran_stalker'\\n### PERSONALITY: You are gruff_but_fair.\\n### CURRENT REPUTATION: 750\\n### CURRENT WEAPON: You are wielding a AK-74\\n</CHARACTER>"},
        {"role": "system", "content": "## INTERACTION RULES: COMBAT AND AGGRESSION\\n\\n1. The Zone is a dangerous place: assume every person is carrying a firearm for self-defence. There are no 'unarmed civilians' in the Zone.\\n2. Do not be overly hostile or aggressive unless provoked, or if you have a reason to be."},
        {"role": "system", "content": "<CONTEXT>\\n"},
        {"role": "system", "content": "## CURRENT LOCATION\\n\\nLocation: Cordon (near Rookie Village)\\nTime: afternoon\\nWeather: clear\\n"},
        {"role": "system", "content": "## DYNAMIC WORLD STATE / NEWS\\n\\nGeneral Voronin, leader of Duty, is dead.\\n\\nThe Military and Loners have an uneasy truce in Cordon. The Military controls the southern checkpoint but allows stalkers through as long as they don't cause trouble.\\n"},
        {"role": "system", "content": "## LONG-TERM MEMORIES\\n\\n<MEMORIES>\\nWolf had been patrolling the Cordon for three days.\\n</MEMORIES>"},
        {"role": "system", "content": "## Events\\n\\n<EVENTS>\\n"},
        {"role": "system", "content": "### CURRENT EVENTS\\n(from oldest to newest):\\n"},
        {"role": "user", "content": "Wolf (Veteran, Loner, Reputation: 750) spotted Bloodsucker (Monster)"},
        {"role": "user", "content": "Wolf (Veteran, Loner, Reputation: 750) killed Bandit_001 (Experienced, Bandit, Reputation: -300)"},
        {"role": "system", "content": "</EVENTS>\\n\\n"},
        {"role": "system", "content": "</CONTEXT>\\n\\n"},
        {"role": "system", "content": "## `CONTEXT` SECTION: USE GUIDELINES\\n\\n0. **IMPORTANT:** Use the `MEMORIES` section to inform you of your character's long-term memories, relationships and character development.\\n1. **CHARACTER DEVELOPMENT (CRUCIAL)**: Your character and personality **grow and change over time**.\\n2. **SUBTLETY:** Use the `CONTEXT` section to **SUBTLY** inform your response.\\n3. Use any 'TIME GAP' event to help establish a timeline.\\n4. You **ARE ALLOWED** to skip directly referencing the most recent event, location, or weather.\\n5. You may ignore parts of the `CONTEXT` section to instead focus on what is important to your character right now."},
        {"role": "system", "content": "## FINAL INSTRUCTION\\n\\n### **TASK:**\\nWrite the next line of dialogue speaking as Wolf."}
    ],
    "options": {"temperature": 0.8, "max_tokens": 200}
}"""
        
        # =====================================================================
        # 13) LLM DIALOGUE RESPONSE
        # =====================================================================
        LLM_DIALOGUE_RESPONSE = """Another bandit down. Good riddance."""
        
        # =====================================================================
        # 14) PUBLISH REQUEST (ZMQ to Lua)
        # =====================================================================
        PUBLISH_REQUEST = """
        {
            "topic": "dialogue.display",
            "payload": {
                "speaker_id": "12345",
                "dialogue": "Another bandit down. Good riddance.",
                "create_event": true
            }
        }
        """
        
        # =====================================================================
        # RUN LIFECYCLE
        # =====================================================================
        snapshot = await run_lifecycle(
            input_event_json=INPUT_EVENT,
            scene_json=SCENE_CONTEXT_RESPONSE,
            characters_alive_json=CHARACTERS_ALIVE_RESPONSE,
            memory_json=MEMORY_RESPONSE,
            character_json=CHARACTER_RESPONSE,
            llm_responses=[LLM_SPEAKER_RESPONSE, LLM_DIALOGUE_RESPONSE],
        )
        
        # =====================================================================
        # ASSERTIONS - Verify lifecycle executed correctly
        # =====================================================================
        # Input event parsed correctly
        assert snapshot.input_event == json.loads(INPUT_EVENT)
        
        # State requests match expected (verify method names and args)
        expected_state_requests = [
            json.loads(MEMORY_REQUEST),
            json.loads(CHARACTER_REQUEST),
            json.loads(SCENE_CONTEXT_REQUEST),
            json.loads(CHARACTERS_ALIVE_REQUEST),
        ]
        assert len(snapshot.state_requests) == len(expected_state_requests), \
            f"Expected {len(expected_state_requests)} state requests, got {len(snapshot.state_requests)}"
        for i, (actual, expected) in enumerate(zip(snapshot.state_requests, expected_state_requests)):
            assert actual == expected, f"State request {i} mismatch:\nExpected: {expected}\nActual: {actual}"
        
        # LLM requests - deep comparison
        assert len(snapshot.llm_requests) == 2, f"Expected 2 LLM calls, got {len(snapshot.llm_requests)}"
        
        expected_speaker_req = json.loads(LLM_SPEAKER_REQUEST)
        expected_dialogue_req = json.loads(LLM_DIALOGUE_REQUEST)
        
        assert snapshot.llm_requests[0] == expected_speaker_req, \
            f"Speaker request mismatch:\nExpected: {json.dumps(expected_speaker_req, indent=2)}\nActual: {json.dumps(snapshot.llm_requests[0], indent=2)}"
        assert snapshot.llm_requests[1] == expected_dialogue_req, \
            f"Dialogue request mismatch:\nExpected: {json.dumps(expected_dialogue_req, indent=2)}\nActual: {json.dumps(snapshot.llm_requests[1], indent=2)}"
        
        # Published output matches expected
        assert_published(snapshot.published, json.dumps([json.loads(PUBLISH_REQUEST)]))
        assert_published(snapshot.published, json.dumps([json.loads(PUBLISH_REQUEST)]))
