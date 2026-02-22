"""Integration tests for CALLOUT event handling lifecycle.

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertions |
|------|-----------|----------------|
| test_happy_path | Spotter spots enemy, 2 witnesses | Full lifecycle verification |
| test_missing_target | Only spotter, no target | "Someone spotted an enemy" |
| test_mutant_target | Target is a monster | Monster faction display name |
"""

import json
import pytest

from talker_service.prompts.helpers import describe_event
from talker_service.prompts.models import Event

from tests.integration.conftest import (
    run_lifecycle,
    assert_llm_requests,
    assert_published,
)


_SCENE = json.dumps({
    "loc": "l01_escape",
    "poi": "Rookie Village",
    "time": {"Y": 2012, "M": 6, "D": 15, "h": 10, "m": 0, "s": 0, "ms": 0},
    "weather": "foggy",
    "emission": False,
    "psy_storm": False,
    "sheltering": False,
    "campfire": None,
    "brain_scorcher_disabled": False,
    "miracle_machine_disabled": False,
})
_EMPTY_MEMORY = json.dumps({"narrative": None, "last_update_time_ms": 0})
_EMPTY_ALIVE = json.dumps({"alive": {}})


# =============================================================================
# HAPPY PATH TEST
# =============================================================================

class TestCalloutLifecycle:
    """CALLOUT lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_spotter_spots_enemy(self):
        """Wolf spots a Bloodsucker; 2 witnesses (Wolf + Petruha) react."""

        INPUT_EVENT = """
        {
            "event": {
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
            "is_important": false
        }
        """

        LLM_SPEAKER_RESPONSE = """{"id": 12345}"""

        CHARACTER_RESPONSE = json.dumps({
            "game_id": 12345,
            "name": "Wolf",
            "faction": "stalker",
            "experience": "Veteran",
            "reputation": 750,
            "personality": "gruff_but_fair",
            "backstory": "veteran_stalker",
            "weapon": "AK-74",
            "visual_faction": None,
        })

        LLM_DIALOGUE_RESPONSE = """Eyes open, that thing won't go down easy."""

        snapshot = await run_lifecycle(
            input_event_json=INPUT_EVENT,
            scene_json=_SCENE,
            characters_alive_json=_EMPTY_ALIVE,
            memory_json=_EMPTY_MEMORY,
            character_json=CHARACTER_RESPONSE,
            llm_responses=[LLM_SPEAKER_RESPONSE, LLM_DIALOGUE_RESPONSE],
        )

        assert len(snapshot.llm_requests) == 2
        assert len(snapshot.published) == 1
        assert snapshot.published[0]["payload"]["speaker_id"] == "12345"

        assert_llm_requests(
            snapshot.llm_requests,
            json.dumps([
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["spotted|Bloodsucker"]}
                    ],
                    "options": {"temperature": 0.3, "max_tokens": 50}
                },
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["spotted Bloodsucker"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestCalloutDescribeEvent:
    """Edge case tests for CALLOUT describe_event() output."""

    def test_spotter_and_target(self):
        """Normal callout: '{spotter} spotted {target}'."""
        INPUT_EVENT = {
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
                    "game_id": 67890,
                    "name": "Bandit_001",
                    "faction": "bandit",
                    "experience": "Experienced",
                    "reputation": -300
                }
            },
            "game_time_ms": 0,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = (
            "Wolf (Veteran, Loner, Reputation: 750) spotted "
            "Bandit_001 (Experienced, Bandit, Reputation: -300)"
        )

        event = Event.from_dict(INPUT_EVENT)
        assert describe_event(event) == EXPECTED_DESCRIPTION

    def test_mutant_target(self):
        """Monster target shows faction display without stats."""
        INPUT_EVENT = {
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
            "game_time_ms": 0,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = (
            "Wolf (Veteran, Loner, Reputation: 750) spotted Bloodsucker (Monster)"
        )

        event = Event.from_dict(INPUT_EVENT)
        assert describe_event(event) == EXPECTED_DESCRIPTION

    def test_missing_target(self):
        """Missing target context falls back to 'Someone spotted an enemy'."""
        INPUT_EVENT = {
            "type": "CALLOUT",
            "context": {
                "spotter": {
                    "game_id": 12345,
                    "name": "Wolf",
                    "faction": "stalker",
                    "experience": "Veteran",
                    "reputation": 750
                }
            },
            "game_time_ms": 0,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = "Someone spotted an enemy"

        event = Event.from_dict(INPUT_EVENT)
        assert describe_event(event) == EXPECTED_DESCRIPTION
