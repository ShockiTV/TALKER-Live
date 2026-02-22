"""Integration tests for TAUNT event handling lifecycle.

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertions |
|------|-----------|----------------|
| test_happy_path | Bandit taunts, 2 witnesses react | Full lifecycle verification |
| test_taunter_present | Normal taunter | "{taunter} taunted their enemies" |
| test_missing_taunter | No taunter in context | "Someone taunted their enemies" |
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
    "loc": "l02_garbage",
    "poi": None,
    "time": {"Y": 2012, "M": 6, "D": 15, "h": 12, "m": 0, "s": 0, "ms": 0},
    "weather": "overcast",
    "emission": False,
    "psy_storm": False,
    "sheltering": False,
    "campfire": None,
    "brain_scorcher_disabled": False,
    "miracle_machine_disabled": False,
})
_EMPTY_MEMORY = json.dumps({"narrative": None, "last_update_time_ms": 0, "new_events": []})
_EMPTY_ALIVE = json.dumps({"alive": {}})


class TestTauntLifecycle:
    """TAUNT lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_bandit_taunts(self):
        """Bandit Butcher taunts; 2 Loner witnesses react (Wolf selected)."""

        INPUT_EVENT = """
        {
            "event": {
                "type": "TAUNT",
                "context": {
                    "taunter": {
                        "game_id": 55555,
                        "name": "Butcher",
                        "faction": "bandit",
                        "experience": "Veteran",
                        "reputation": -800
                    }
                },
                "game_time_ms": 2500000,
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

        LLM_DIALOGUE_RESPONSE = """Ignore him. Bandits like that prey on rookies who take the bait."""

        snapshot = await run_lifecycle(
            input_event_json=INPUT_EVENT,
            scene_json=_SCENE,
            characters_alive_json=_EMPTY_ALIVE,
            memory_json=_EMPTY_MEMORY,
            character_json=CHARACTER_RESPONSE,
            llm_responses=[LLM_SPEAKER_RESPONSE, LLM_DIALOGUE_RESPONSE],
        )

        assert len(snapshot.llm_requests) == 2
        assert snapshot.published[0]["payload"]["speaker_id"] == "12345"

        assert_llm_requests(
            snapshot.llm_requests,
            json.dumps([
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["taunted"]}
                    ],
                    "options": {"temperature": 0.3, "max_tokens": 50}
                },
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["Butcher.*taunted"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


class TestTauntDescribeEvent:
    """Edge case tests for TAUNT describe_event() output."""

    def test_taunter_present(self):
        """Normal taunter: '{taunter} taunted their enemies'."""
        INPUT_EVENT = {
            "type": "TAUNT",
            "context": {
                "taunter": {
                    "game_id": 55555,
                    "name": "Butcher",
                    "faction": "bandit",
                    "experience": "Veteran",
                    "reputation": -800
                }
            },
            "game_time_ms": 0,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = "Butcher (Veteran, Bandit, Reputation: -800) taunted their enemies"

        event = Event.from_dict(INPUT_EVENT)
        assert describe_event(event) == EXPECTED_DESCRIPTION

    def test_missing_taunter(self):
        """No taunter falls back to 'Someone taunted their enemies'."""
        INPUT_EVENT = {
            "type": "TAUNT",
            "context": {},
            "game_time_ms": 0,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = "Someone taunted their enemies"

        event = Event.from_dict(INPUT_EVENT)
        assert describe_event(event) == EXPECTED_DESCRIPTION
