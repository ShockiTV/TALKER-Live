"""Integration tests for EMISSION event handling lifecycle.

EMISSION is a static event — no character context, fixed description.
Witnesses react to the sweeping emission.

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertions |
|------|-----------|----------------|
| test_happy_path | Emission event, witnesses react | Full lifecycle verification |
| test_static_description | No context fields | "An emission swept through the Zone" |
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
    "poi": None,
    "time": {"Y": 2012, "M": 6, "D": 15, "h": 20, "m": 0, "s": 0, "ms": 0},
    "weather": "thunderstorm",
    "emission": True,
    "psy_storm": False,
    "sheltering": False,
    "campfire": None,
    "brain_scorcher_disabled": False,
    "miracle_machine_disabled": False,
})
_EMPTY_MEMORY = json.dumps({"narrative": None, "last_update_time_ms": 0, "new_events": []})
_EMPTY_ALIVE = json.dumps({"alive": {}})


class TestEmissionLifecycle:
    """EMISSION lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_emission_sweeps(self):
        """Emission event; 2 witnesses (Wolf + Petruha) react, Wolf selected."""

        INPUT_EVENT = """
        {
            "event": {
                "type": "EMISSION",
                "context": {},
                "game_time_ms": 6000000,
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

        LLM_DIALOGUE_RESPONSE = """Get to cover, now! This one's going to be bad."""

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
                        {"role": "user", "content_patterns": ["emission"]}
                    ],
                    "options": {"temperature": 0.3, "max_tokens": 50}
                },
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["emission swept"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


class TestEmissionDescribeEvent:
    """describe_event() output for EMISSION (static)."""

    def test_static_description(self):
        """EMISSION always produces the same static string."""
        INPUT_EVENT = {
            "type": "EMISSION",
            "context": {},
            "game_time_ms": 0,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = "An emission swept through the Zone"

        event = Event.from_dict(INPUT_EVENT)
        assert describe_event(event) == EXPECTED_DESCRIPTION

    def test_ignores_context_fields(self):
        """Extra context fields don't change the static EMISSION description."""
        INPUT_EVENT = {
            "type": "EMISSION",
            "context": {"extra_field": "ignored", "another": 123},
            "game_time_ms": 0,
            "flags": {}
        }
        event = Event.from_dict(INPUT_EVENT)
        assert describe_event(event) == "An emission swept through the Zone"
