"""Integration tests for MAP_TRANSITION event handling lifecycle.

Tests the full event lifecycle from ZMQ input through dialogue generation to output,
with focus on MAP_TRANSITION-specific behavior (location resolution, visit count
formatting, companion list formatting).

================================================================================
TEST STRUCTURE GUIDE
================================================================================

This file follows the same JSON constant pattern as test_event_lifecycle.py:

**Happy Path Test:**
- Full 14-step JSON visibility showing complete lifecycle

**Edge Case Tests:**
- INPUT_EVENT: The MAP_TRANSITION event context being tested
- EXPECTED_DESCRIPTION: The complete expected describe_event() output string

================================================================================
MAP_TRANSITION CONTEXT FIELDS
================================================================================

Required fields:
- actor: Character performing the travel
- source: Technical location ID (e.g., "l01_escape")
- destination: Technical location ID (e.g., "l02_garbage")

Optional fields:
- visit_count: Number of times destination has been visited (affects description)
- companions: List of companion characters (affects description)

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertion |
|------|-----------|---------------|
| happy_path | Full lifecycle | Complete 14-step verification |
| visit_count_first_time | visit_count=1 | "for the first time" |
| visit_count_second_time | visit_count=2 | "for the 2nd time" |
| visit_count_third_time | visit_count=3 | "for the 3rd time" |
| visit_count_many_times | visit_count=5 | "again" |
| no_companions | companions=[] | No "travelling companions" |
| multiple_companions | 2 companions | "Hip and Fanatic" |
| unknown_destination | unknown ID | Technical ID fallback |
| empty_source | source="" | "somewhere" fallback |
"""

import json
import pytest
from dataclasses import dataclass
from typing import Any

from talker_service.dialogue.generator import DialogueGenerator
from talker_service.prompts.helpers import describe_event
from talker_service.prompts.models import Event
from talker_service.state.batch import BatchResult


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

    async def execute_batch(self, batch) -> "BatchResult":
        """Route batch sub-queries to individual mock methods, recording requests."""
        results: dict[str, dict] = {}
        for q in batch.build():
            qid = q["id"]
            resource = q["resource"]
            params = q.get("params", {})
            try:
                if resource == "store.memories":
                    self.requests.append({
                        "method": "query_memories",
                        "args": {"character_id": params["character_id"]}
                    })
                    results[qid] = {"ok": True, "data": self.memory_response}
                elif resource == "query.character":
                    self.requests.append({
                        "method": "query_character",
                        "args": {"character_id": params["id"]}
                    })
                    results[qid] = {"ok": True, "data": self.character_response}
                elif resource == "query.world":
                    self.requests.append({
                        "method": "query_world_context",
                        "args": {}
                    })
                    results[qid] = {"ok": True, "data": self.scene_response}
                elif resource == "query.characters_alive":
                    ids = params.get("ids", [])
                    self.requests.append({
                        "method": "query_characters_alive",
                        "args": {"story_ids": ids}
                    })
                    alive_data = self.characters_alive_response.get("alive", {})
                    results[qid] = {"ok": True, "data": alive_data}
                else:
                    results[qid] = {"ok": False, "error": f"unknown resource: {resource}"}
            except Exception as e:
                results[qid] = {"ok": False, "error": str(e)}
        return BatchResult(results)


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


def assert_published(actual: list[dict], expected_json: str) -> None:
    """Assert published commands match expected JSON."""
    expected = json.loads(expected_json)
    assert len(actual) == len(expected), f"Expected {len(expected)} published, got {len(actual)}"
    for i, (act, exp) in enumerate(zip(actual, expected)):
        assert act["topic"] == exp["topic"], f"Publish {i}: topic mismatch"
        for key, val in exp["payload"].items():
            assert act["payload"].get(key) == val, f"Publish {i}: payload.{key} mismatch"


# =============================================================================
# HAPPY PATH TEST (FULL 14-STEP JSON VISIBILITY)
# =============================================================================

class TestMapTransitionLifecycle:
    """MAP_TRANSITION lifecycle tests with full JSON visibility for happy path."""
    
    @pytest.mark.asyncio
    async def test_happy_path_with_companions(self):
        """Happy path: Player with companion travels to Garbage for first time.
        
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
                "type": "MAP_TRANSITION",
                "context": {
                    "actor": {
                        "game_id": 0,
                        "name": "Marked One",
                        "faction": "stalker",
                        "experience": "Experienced",
                        "reputation": 500
                    },
                    "source": "l01_escape",
                    "destination": "l02_garbage",
                    "visit_count": 1,
                    "companions": [
                        {
                            "game_id": 11111,
                            "name": "Hip",
                            "faction": "stalker",
                            "experience": "Experienced",
                            "reputation": 200,
                            "personality": "generic.28"
                        },
                        {
                            "game_id": 22222,
                            "name": "Fanatic",
                            "faction": "stalker",
                            "experience": "Veteran",
                            "reputation": 400,
                            "personality": "generic.31"
                        }
                    ]
                },
                "game_time_ms": 3000000,
                "witnesses": [
                    {
                        "game_id": 11111,
                        "name": "Hip",
                        "faction": "stalker",
                        "experience": "Experienced",
                        "reputation": 200,
                        "personality": "generic.28"
                    },
                    {
                        "game_id": 22222,
                        "name": "Fanatic",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 400,
                        "personality": "generic.31"
                    }
                ],
                "flags": {}
            },
            "is_important": true
        }
        """
        
        # =====================================================================
        # 2) LLM SPEAKER REQUEST
        # Uses witnesses from event directly (no state query needed)
        # =====================================================================
        # Note: We verify content in assertions rather than exact match
        # because the full prompt contains dynamic elements
        
        # =====================================================================
        # 3) LLM SPEAKER RESPONSE
        # =====================================================================
        LLM_SPEAKER_RESPONSE = """{"id": 11111}"""
        
        # =====================================================================
        # 4) MEMORY QUERY REQUEST (for selected speaker)
        # =====================================================================
        MEMORY_REQUEST = """
        {
            "method": "query_memories",
            "args": {"character_id": "11111"}
        }
        """
        
        # =====================================================================
        # 5) MEMORY QUERY RESPONSE
        # =====================================================================
        MEMORY_RESPONSE = """
        {
            "narrative": "Hip has been travelling with Marked One for a few days.",
            "last_update_time_ms": 2500000,
            "new_events": []
        }
        """
        
        # =====================================================================
        # 6) CHARACTER QUERY REQUEST (for selected speaker)
        # =====================================================================
        CHARACTER_REQUEST = """
        {
            "method": "query_character",
            "args": {"character_id": "11111"}
        }
        """
        
        # =====================================================================
        # 7) CHARACTER QUERY RESPONSE
        # =====================================================================
        CHARACTER_RESPONSE = """
        {
            "game_id": 11111,
            "name": "Hip",
            "faction": "stalker",
            "experience": "Experienced",
            "reputation": 200,
            "personality": "curious_explorer",
            "backstory": "former_student",
            "weapon": "MP5",
            "visual_faction": "stalker"
        }
        """
        
        # =====================================================================
        # 8) SCENE/WORLD CONTEXT QUERY REQUEST
        # =====================================================================
        SCENE_CONTEXT_REQUEST = """
        {
            "method": "query_world_context",
            "args": {}
        }
        """
        
        # =====================================================================
        # 9) SCENE/WORLD CONTEXT QUERY RESPONSE (now at Garbage)
        # =====================================================================
        SCENE_CONTEXT_RESPONSE = """
        {
            "loc": "l02_garbage",
            "poi": "Truck depot",
            "time": {"Y": 2012, "M": 6, "D": 15, "h": 16, "m": 0, "s": 0, "ms": 0},
            "weather": "cloudy",
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
        # =====================================================================
        CHARACTERS_ALIVE_REQUEST = """
        {
            "method": "query_characters_alive",
            "args": {
                "story_ids": [
                    "agr_smart_terrain_1_6_near_2_military_colonel_kovalski",
                    "bar_dolg_leader",
                    "cit_killers_merc_trader_stalker",
                    "ds_domik_isg_leader",
                    "gen_greh_sabaoth",
                    "hunter_gar_trader",
                    "jup_depo_isg_leader",
                    "kat_greh_sabaoth",
                    "lider_monolith_haron",
                    "mar_smart_terrain_base_stalker_leader_marsh",
                    "mil_smart_terrain_7_7_freedom_leader_stalker",
                    "sar_greh_sabaoth",
                    "yan_stalker_sakharov",
                    "zat_b7_bandit_boss_sultan"
                ]
            }
        }
        """
        
        # =====================================================================
        # 11) CHARACTERS ALIVE QUERY RESPONSE
        # =====================================================================
        CHARACTERS_ALIVE_RESPONSE = """
        {
            "alive": {
                "agr_smart_terrain_1_6_near_2_military_colonel_kovalski": true,
                "bar_dolg_leader": true,
                "cit_killers_merc_trader_stalker": true,
                "ds_domik_isg_leader": true,
                "gen_greh_sabaoth": true,
                "hunter_gar_trader": false,
                "jup_depo_isg_leader": true,
                "kat_greh_sabaoth": true,
                "lider_monolith_haron": true,
                "mar_smart_terrain_base_stalker_leader_marsh": true,
                "mil_smart_terrain_7_7_freedom_leader_stalker": true,
                "sar_greh_sabaoth": true,
                "yan_stalker_sakharov": true,
                "zat_b7_bandit_boss_sultan": true
            }
        }
        """
        
        # =====================================================================
        # 12) LLM DIALOGUE REQUEST
        # Messages sent to LLM for dialogue generation
        # Contains speaker personality, backstory, recent events
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
        {"role": "system", "content": "## CHARACTER ANCHOR (CORE IDENTITY)\\n\\n### CHARACTER ANCHOR USE GUIDELINES:\\n0. **INTERNAL MONOLOGUE VS EXTERNAL ACTION:** Your traits define your **MINDSET**. They do **NOT** require you to narrate the action.\\n1. **SUBTLETY:** The 'DEFINING CHARACTER TRAIT/BACKSTORY' should inform your characterisation subtly. Do not explicitly reference it in every response.\\n2. **PRIORITY:** Your individual personality always takes precedence over general faction traits.\\n3. AVOID talking about your weapon unless directly asked about it, or you have a **GOOD** reason to do so.\\n\\n### CHARACTER DETAILS:\\n<CHARACTER>\\n### NAME: Hip\\n### RANK: Experienced\\n### FACTION: Loner\\n### FACTION DESCRIPTION: Independent stalkers (Loners) who survive in the Zone through scavenging, artifact hunting, and odd jobs. No central leadership, just mutual aid.\\n### BACKSTORY ANCHOR/DEFINING CHARACTER TRAIT (IMPORTANT): 'former_student'\\n### PERSONALITY: You are curious_explorer.\\n### CURRENT REPUTATION: 200\\n### CURRENT WEAPON: You are wielding a MP5\\n</CHARACTER>"},
        {"role": "system", "content": "## INTERACTION RULES: COMBAT AND AGGRESSION\\n\\n1. The Zone is a dangerous place: assume every person is carrying a firearm for self-defence. There are no 'unarmed civilians' in the Zone.\\n2. Do not be overly hostile or aggressive unless provoked, or if you have a reason to be."},
        {"role": "system", "content": "<CONTEXT>\\n"},
        {"role": "system", "content": "## CURRENT LOCATION\\n\\nLocation: Garbage (near Truck depot)\\nTime: afternoon\\nWeather: cloudy\\n"},
        {"role": "system", "content": "## DYNAMIC WORLD STATE / NEWS\\n\\nButcher, Mutant hunter and trader in Garbage offering good money for mutant parts, is dead.\\n"},
        {"role": "system", "content": "## LONG-TERM MEMORIES\\n\\n<MEMORIES>\\nHip has been travelling with Marked One for a few days.\\n</MEMORIES>"},
        {"role": "system", "content": "## Events\\n\\n<EVENTS>\\n"},
        {"role": "system", "content": "### CURRENT EVENTS\\n(from oldest to newest):\\n"},
        {"role": "user", "content": "Marked One (Experienced, Loner, Reputation: 500) and their travelling companions Hip and Fanatic traveled from Cordon to Garbage for the first time. Garbage (an area connecting the Cordon to Rostok) is an area where radioactive trash heaps and broken machinery from the 1986 disaster was dumped. It houses Butcher's shop in an old train depot, and its south-central location means roaming Loners and Bandits are common."},
        {"role": "system", "content": "</EVENTS>\\n\\n"},
        {"role": "system", "content": "</CONTEXT>\\n\\n"},
        {"role": "system", "content": "## `CONTEXT` SECTION: USE GUIDELINES\\n\\n0. **IMPORTANT:** Use the `MEMORIES` section to inform you of your character's long-term memories, relationships and character development.\\n1. **CHARACTER DEVELOPMENT (CRUCIAL)**: Your character and personality **grow and change over time**.\\n2. **SUBTLETY:** Use the `CONTEXT` section to **SUBTLY** inform your response.\\n3. Use any 'TIME GAP' event to help establish a timeline.\\n4. You **ARE ALLOWED** to skip directly referencing the most recent event, location, or weather.\\n5. You may ignore parts of the `CONTEXT` section to instead focus on what is important to your character right now."},
        {"role": "system", "content": "## FINAL INSTRUCTION\\n\\n### **TASK:**\\nWrite the next line of dialogue speaking as Hip."}
    ],
    "options": {"temperature": 0.8, "max_tokens": 200}
}"""
        
        # =====================================================================
        # 13) LLM DIALOGUE RESPONSE
        # =====================================================================
        LLM_DIALOGUE_RESPONSE = """Finally, we made it to Garbage. First time here, better stay alert."""
        
        # =====================================================================
        # 14) PUBLISH REQUEST (ZMQ to Lua)
        # =====================================================================
        PUBLISH_REQUEST = """
        {
            "topic": "dialogue.display",
            "payload": {
                "speaker_id": "11111",
                "dialogue": "Finally, we made it to Garbage. First time here, better stay alert.",
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
        # ASSERTIONS
        # =====================================================================
        # Input event parsed correctly
        assert snapshot.input_event == json.loads(INPUT_EVENT)
        
        # Verify state requests were made
        assert len(snapshot.state_requests) >= 3, \
            f"Expected at least 3 state requests, got {len(snapshot.state_requests)}"
        
        # Verify LLM was called twice (speaker selection + dialogue generation)
        assert len(snapshot.llm_requests) == 2, f"Expected 2 LLM calls, got {len(snapshot.llm_requests)}"
        
        # Step 2: Verify speaker selection request contains MAP_TRANSITION info
        speaker_prompt_content = " ".join(
            m["content"] for m in snapshot.llm_requests[0]["messages"]
        )
        assert "MAP_TRANSITION" in speaker_prompt_content or "traveled" in speaker_prompt_content, \
            "Expected MAP_TRANSITION event in speaker selection prompt"
        assert "Hip" in speaker_prompt_content, \
            "Expected witness 'Hip' in speaker selection prompt"
        assert "Fanatic" in speaker_prompt_content, \
            "Expected witness 'Fanatic' in speaker selection prompt"
        
        # Step 12: Verify dialogue request matches expected structure exactly
        expected_dialogue_req = json.loads(LLM_DIALOGUE_REQUEST)
        actual_dialogue_req = snapshot.llm_requests[1]
        
        assert actual_dialogue_req == expected_dialogue_req, \
            f"Dialogue request mismatch:\nExpected:\n{json.dumps(expected_dialogue_req, indent=2)}\n\nActual:\n{json.dumps(actual_dialogue_req, indent=2)}"
        
        # Verify dialogue was published
        assert len(snapshot.published) == 1, f"Expected 1 published message, got {len(snapshot.published)}"
        assert snapshot.published[0]["topic"] == "dialogue.display"


# =============================================================================
# EDGE CASE TESTS (INPUT_EVENT + EXPECTED_DESCRIPTION pattern)
# =============================================================================

class TestMapTransitionDescribeEvent:
    """Edge case tests for MAP_TRANSITION describe_event() output.
    
    Each test defines:
    - INPUT_EVENT: The event context being tested
    - EXPECTED_DESCRIPTION: The complete expected output from describe_event()
    """
    
    def test_visit_count_first_time(self):
        """visit_count=1 produces 'for the first time'."""
        
        INPUT_EVENT = """
        {
            "type": "MAP_TRANSITION",
            "context": {
                "actor": {
                    "game_id": 0,
                    "name": "Marked One",
                    "faction": "stalker",
                    "experience": "Experienced",
                    "reputation": 500
                },
                "source": "l01_escape",
                "destination": "l02_garbage",
                "visit_count": 1,
                "companions": []
            },
            "game_time_ms": 3000000,
            "flags": {}
        }
        """
        
        EXPECTED_DESCRIPTION = "Marked One (Experienced, Loner, Reputation: 500) traveled from Cordon to Garbage for the first time. Garbage (an area connecting the Cordon to Rostok) is an area where radioactive trash heaps and broken machinery from the 1986 disaster was dumped. It houses Butcher's shop in an old train depot, and its south-central location means roaming Loners and Bandits are common."
        
        event_data = json.loads(INPUT_EVENT)
        event = Event.from_dict(event_data)
        result = describe_event(event)
        
        assert result == EXPECTED_DESCRIPTION, \
            f"Expected:\n{EXPECTED_DESCRIPTION}\n\nGot:\n{result}"
    
    def test_visit_count_second_time(self):
        """visit_count=2 produces 'for the 2nd time'."""
        
        INPUT_EVENT = """
        {
            "type": "MAP_TRANSITION",
            "context": {
                "actor": {
                    "game_id": 0,
                    "name": "Marked One",
                    "faction": "stalker",
                    "experience": "Experienced",
                    "reputation": 500
                },
                "source": "l01_escape",
                "destination": "l02_garbage",
                "visit_count": 2,
                "companions": []
            },
            "game_time_ms": 3000000,
            "flags": {}
        }
        """
        
        EXPECTED_DESCRIPTION = "Marked One (Experienced, Loner, Reputation: 500) traveled from Cordon to Garbage for the 2nd time. Garbage (an area connecting the Cordon to Rostok) is an area where radioactive trash heaps and broken machinery from the 1986 disaster was dumped. It houses Butcher's shop in an old train depot, and its south-central location means roaming Loners and Bandits are common."
        
        event_data = json.loads(INPUT_EVENT)
        event = Event.from_dict(event_data)
        result = describe_event(event)
        
        assert result == EXPECTED_DESCRIPTION, \
            f"Expected:\n{EXPECTED_DESCRIPTION}\n\nGot:\n{result}"
    
    def test_visit_count_third_time(self):
        """visit_count=3 produces 'for the 3rd time'."""
        
        INPUT_EVENT = """
        {
            "type": "MAP_TRANSITION",
            "context": {
                "actor": {
                    "game_id": 0,
                    "name": "Marked One",
                    "faction": "stalker",
                    "experience": "Experienced",
                    "reputation": 500
                },
                "source": "l01_escape",
                "destination": "l02_garbage",
                "visit_count": 3,
                "companions": []
            },
            "game_time_ms": 3000000,
            "flags": {}
        }
        """
        
        EXPECTED_DESCRIPTION = "Marked One (Experienced, Loner, Reputation: 500) traveled from Cordon to Garbage for the 3rd time. Garbage (an area connecting the Cordon to Rostok) is an area where radioactive trash heaps and broken machinery from the 1986 disaster was dumped. It houses Butcher's shop in an old train depot, and its south-central location means roaming Loners and Bandits are common."
        
        event_data = json.loads(INPUT_EVENT)
        event = Event.from_dict(event_data)
        result = describe_event(event)
        
        assert result == EXPECTED_DESCRIPTION, \
            f"Expected:\n{EXPECTED_DESCRIPTION}\n\nGot:\n{result}"
    
    def test_visit_count_many_times(self):
        """visit_count>=4 produces 'again'."""
        
        INPUT_EVENT = """
        {
            "type": "MAP_TRANSITION",
            "context": {
                "actor": {
                    "game_id": 0,
                    "name": "Marked One",
                    "faction": "stalker",
                    "experience": "Experienced",
                    "reputation": 500
                },
                "source": "l01_escape",
                "destination": "l02_garbage",
                "visit_count": 5,
                "companions": []
            },
            "game_time_ms": 3000000,
            "flags": {}
        }
        """
        
        EXPECTED_DESCRIPTION = "Marked One (Experienced, Loner, Reputation: 500) traveled from Cordon to Garbage again. Garbage (an area connecting the Cordon to Rostok) is an area where radioactive trash heaps and broken machinery from the 1986 disaster was dumped. It houses Butcher's shop in an old train depot, and its south-central location means roaming Loners and Bandits are common."
        
        event_data = json.loads(INPUT_EVENT)
        event = Event.from_dict(event_data)
        result = describe_event(event)
        
        assert result == EXPECTED_DESCRIPTION, \
            f"Expected:\n{EXPECTED_DESCRIPTION}\n\nGot:\n{result}"
    
    def test_no_companions(self):
        """Empty companions list produces no 'travelling companions' text."""
        
        INPUT_EVENT = """
        {
            "type": "MAP_TRANSITION",
            "context": {
                "actor": {
                    "game_id": 0,
                    "name": "Marked One",
                    "faction": "stalker",
                    "experience": "Experienced",
                    "reputation": 500
                },
                "source": "l01_escape",
                "destination": "l02_garbage",
                "visit_count": 1,
                "companions": []
            },
            "game_time_ms": 3000000,
            "flags": {}
        }
        """
        
        EXPECTED_DESCRIPTION = "Marked One (Experienced, Loner, Reputation: 500) traveled from Cordon to Garbage for the first time. Garbage (an area connecting the Cordon to Rostok) is an area where radioactive trash heaps and broken machinery from the 1986 disaster was dumped. It houses Butcher's shop in an old train depot, and its south-central location means roaming Loners and Bandits are common."
        
        event_data = json.loads(INPUT_EVENT)
        event = Event.from_dict(event_data)
        result = describe_event(event)
        
        assert "travelling companions" not in result, \
            f"Expected no 'travelling companions' in result:\n{result}"
        assert result == EXPECTED_DESCRIPTION, \
            f"Expected:\n{EXPECTED_DESCRIPTION}\n\nGot:\n{result}"
    
    def test_multiple_companions(self):
        """Two companions produces 'Hip and Fanatic'."""
        
        INPUT_EVENT = """
        {
            "type": "MAP_TRANSITION",
            "context": {
                "actor": {
                    "game_id": 0,
                    "name": "Marked One",
                    "faction": "stalker",
                    "experience": "Experienced",
                    "reputation": 500
                },
                "source": "l01_escape",
                "destination": "l02_garbage",
                "visit_count": 1,
                "companions": [
                    {"game_id": 11111, "name": "Hip", "faction": "stalker", "experience": "Experienced", "reputation": 200},
                    {"game_id": 22222, "name": "Fanatic", "faction": "stalker", "experience": "Veteran", "reputation": 400}
                ]
            },
            "game_time_ms": 3000000,
            "flags": {}
        }
        """
        
        EXPECTED_DESCRIPTION = "Marked One (Experienced, Loner, Reputation: 500) and their travelling companions Hip and Fanatic traveled from Cordon to Garbage for the first time. Garbage (an area connecting the Cordon to Rostok) is an area where radioactive trash heaps and broken machinery from the 1986 disaster was dumped. It houses Butcher's shop in an old train depot, and its south-central location means roaming Loners and Bandits are common."
        
        event_data = json.loads(INPUT_EVENT)
        event = Event.from_dict(event_data)
        result = describe_event(event)
        
        assert "Hip and Fanatic" in result, \
            f"Expected 'Hip and Fanatic' in result:\n{result}"
        assert result == EXPECTED_DESCRIPTION, \
            f"Expected:\n{EXPECTED_DESCRIPTION}\n\nGot:\n{result}"
    
    def test_unknown_destination(self):
        """Unknown destination ID uses technical ID as fallback, no description."""
        
        INPUT_EVENT = """
        {
            "type": "MAP_TRANSITION",
            "context": {
                "actor": {
                    "game_id": 0,
                    "name": "Marked One",
                    "faction": "stalker",
                    "experience": "Experienced",
                    "reputation": 500
                },
                "source": "l01_escape",
                "destination": "unknown_zone_id",
                "visit_count": 1,
                "companions": []
            },
            "game_time_ms": 3000000,
            "flags": {}
        }
        """
        
        EXPECTED_DESCRIPTION = "Marked One (Experienced, Loner, Reputation: 500) traveled from Cordon to unknown_zone_id for the first time"
        
        event_data = json.loads(INPUT_EVENT)
        event = Event.from_dict(event_data)
        result = describe_event(event)
        
        assert result == EXPECTED_DESCRIPTION, \
            f"Expected:\n{EXPECTED_DESCRIPTION}\n\nGot:\n{result}"
    
    def test_empty_source(self):
        """Empty source string uses 'somewhere' as fallback."""
        
        INPUT_EVENT = """
        {
            "type": "MAP_TRANSITION",
            "context": {
                "actor": {
                    "game_id": 0,
                    "name": "Marked One",
                    "faction": "stalker",
                    "experience": "Experienced",
                    "reputation": 500
                },
                "source": "",
                "destination": "l02_garbage",
                "visit_count": 1,
                "companions": []
            },
            "game_time_ms": 3000000,
            "flags": {}
        }
        """
        
        EXPECTED_DESCRIPTION = "Marked One (Experienced, Loner, Reputation: 500) traveled from somewhere to Garbage for the first time. Garbage (an area connecting the Cordon to Rostok) is an area where radioactive trash heaps and broken machinery from the 1986 disaster was dumped. It houses Butcher's shop in an old train depot, and its south-central location means roaming Loners and Bandits are common."
        
        event_data = json.loads(INPUT_EVENT)
        event = Event.from_dict(event_data)
        result = describe_event(event)
        
        assert result == EXPECTED_DESCRIPTION, \
            f"Expected:\n{EXPECTED_DESCRIPTION}\n\nGot:\n{result}"
