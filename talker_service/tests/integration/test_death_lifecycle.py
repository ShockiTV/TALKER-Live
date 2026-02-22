"""Integration tests for DEATH event handling lifecycle.

Migrates T1 from test_event_lifecycle.py + adds edge cases.

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertions |
|------|-----------|----------------|
| test_happy_path | Full lifecycle (Wolf kills Bandit) | 14-step verification |
| test_no_killer | Victim only (no killer context) | describe_event: "{victim} died" |
| test_unknown_faction_victim | Victim with unrecognized faction | Uses raw faction string |
"""

import json
import pytest

from talker_service.prompts.helpers import describe_event
from talker_service.prompts.models import Event

from tests.integration.conftest import (
    run_lifecycle,
    assert_state_requests,
    assert_llm_requests,
    assert_published,
)


# =============================================================================
# HAPPY PATH TEST (FULL 14-STEP JSON VISIBILITY)
# =============================================================================

class TestDeathLifecycle:
    """DEATH lifecycle tests — migrated from TestEventLifecycleL9 T1."""

    @pytest.mark.asyncio
    async def test_happy_path_wolf_kills_bandit(self):
        """T1: DEATH + Full scene + Dead leader (General Voronin) + Narrative memory.

        Wolf kills Bandit_001 in Cordon. Full 14-step lifecycle:
        1)  Input event (ZMQ from Lua)
        2)  LLM speaker request (witnesses: Wolf + Petruha)
        3)  LLM speaker response — Wolf selected
        4)  Memory query request (for Wolf)
        5)  Memory query response (narrative + CALLOUT event)
        6)  Character query request (for Wolf)
        7)  Character query response
        8)  Scene/world context query request
        9)  Scene/world context query response
        10) Characters alive query request
        11) Characters alive query response (Voronin dead)
        12) LLM dialogue request
        13) LLM dialogue response
        14) Publish request (ZMQ to Lua)
        """

        # =====================================================================
        # 1) INPUT EVENT
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
        # 3) LLM SPEAKER RESPONSE
        # =====================================================================
        LLM_SPEAKER_RESPONSE = """{"id": 12345}"""

        # =====================================================================
        # 5) MEMORY QUERY RESPONSE
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
        # 7) CHARACTER QUERY RESPONSE
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
            "visual_faction": null
        }
        """

        # =====================================================================
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
        # 11) CHARACTERS ALIVE QUERY RESPONSE  (Voronin dead)
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
        # 13) LLM DIALOGUE RESPONSE
        # =====================================================================
        LLM_DIALOGUE_RESPONSE = """Another bandit down. Good riddance."""

        # =====================================================================
        # 14) PUBLISH REQUEST
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
        # ASSERTIONS
        # =====================================================================
        assert snapshot.input_event == json.loads(INPUT_EVENT)

        # State requests: memory, character, world, characters_alive
        assert len(snapshot.state_requests) == 4, \
            f"Expected 4 state requests, got {len(snapshot.state_requests)}"
        assert snapshot.state_requests[0] == {
            "method": "query_memories", "args": {"character_id": "12345"}
        }
        assert snapshot.state_requests[1] == {
            "method": "query_character", "args": {"character_id": "12345"}
        }
        assert snapshot.state_requests[2] == {
            "method": "query_world_context", "args": {}
        }
        assert snapshot.state_requests[3]["method"] == "query_characters_alive"
        assert "esc_2_12_stalker_wolf" in snapshot.state_requests[3]["args"]["story_ids"]

        # LLM calls: speaker selection + dialogue generation
        assert len(snapshot.llm_requests) == 2, \
            f"Expected 2 LLM calls, got {len(snapshot.llm_requests)}"

        # Speaker selection prompt should mention the DEATH event
        speaker_content = " ".join(
            m["content"] for m in snapshot.llm_requests[0]["messages"]
        )
        assert "Wolf" in speaker_content
        assert "Bandit_001" in speaker_content or "killed" in speaker_content

        # Dialogue prompt should contain character info and event
        assert_llm_requests(
            snapshot.llm_requests,
            json.dumps([
                {
                    "messages": [
                        {"role": "system", "content_patterns": ["SPEAKER ID SELECTION"]},
                        {"role": "user", "content_patterns": ["killed", "Bandit"]}
                    ],
                    "options": {"temperature": 0.3, "max_tokens": 50}
                },
                {
                    "messages": [
                        {"role": "system", "content_patterns": ["Wolf", "Veteran", "gruff"]},
                        {"role": "user", "content_patterns": ["Wolf.*killed.*Bandit"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )

        # Published dialogue
        assert_published(
            snapshot.published,
            json.dumps([json.loads(PUBLISH_REQUEST)])
        )


# =============================================================================
# EDGE CASE TESTS (describe_event pattern)
# =============================================================================

class TestDeathDescribeEvent:
    """Edge case tests for DEATH describe_event() output."""

    def test_victim_only_no_killer(self):
        """Victim without killer: '{victim} died'."""
        INPUT_EVENT = {
            "type": "DEATH",
            "context": {
                "victim": {
                    "game_id": 67890,
                    "name": "Bandit_001",
                    "faction": "bandit",
                    "experience": "Experienced",
                    "reputation": -300
                }
            },
            "game_time_ms": 2000000,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = "Bandit_001 (Experienced, Bandit, Reputation: -300) died"

        event = Event.from_dict(INPUT_EVENT)
        result = describe_event(event)
        assert result == EXPECTED_DESCRIPTION, f"Expected:\n{EXPECTED_DESCRIPTION}\n\nGot:\n{result}"

    def test_monster_victim(self):
        """Monster victim shows faction display name without stats."""
        INPUT_EVENT = {
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
                    "game_id": 99999,
                    "name": "Bloodsucker",
                    "faction": "monster",
                    "experience": "Experienced",
                    "reputation": 0
                }
            },
            "game_time_ms": 2000000,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = "Wolf (Veteran, Loner, Reputation: 750) killed Bloodsucker (Monster)"

        event = Event.from_dict(INPUT_EVENT)
        result = describe_event(event)
        assert result == EXPECTED_DESCRIPTION, f"Expected:\n{EXPECTED_DESCRIPTION}\n\nGot:\n{result}"

    def test_no_context(self):
        """Empty context falls back to 'Someone died'."""
        INPUT_EVENT = {
            "type": "DEATH",
            "context": {},
            "game_time_ms": 0,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = "Someone died"

        event = Event.from_dict(INPUT_EVENT)
        result = describe_event(event)
        assert result == EXPECTED_DESCRIPTION
