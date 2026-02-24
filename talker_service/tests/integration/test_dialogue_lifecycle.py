"""Integration tests for DIALOGUE event handling lifecycle.

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertions |
|------|-----------|----------------|
| test_happy_path | NPC says text, 2 witnesses react | Full lifecycle verification |
| test_empty_text | Empty text string | describe_event: '... said: ""' |
| test_long_text | Multi-sentence text | describe_event preserves full text |
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


# Reusable standard mock responses
_SCENE = json.dumps({
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
})

_EMPTY_MEMORY = json.dumps({
    "narrative": None,
    "last_update_time_ms": 0,
})

_EMPTY_ALIVE = json.dumps({"alive": {}})


# =============================================================================
# HAPPY PATH TEST
# =============================================================================

class TestDialogueLifecycle:
    """DIALOGUE lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_npc_speaks(self):
        """NPC Barkeep says something, 2 witnesses (Wolf + Petruha) react.

        DIALOGUE events have a speaker (NPC who spoke) and text.
        Witnesses select who reacts — Wolf selected as speaker.
        """

        # 1) INPUT EVENT
        INPUT_EVENT = """
        {
            "event": {
                "type": "DIALOGUE",
                "context": {
                    "speaker": {
                        "game_id": 33333,
                        "name": "Barkeep",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 800
                    },
                    "text": "Got any good stories from the Zone today?"
                },
                "game_time_ms": 3000000,
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
            "weapon": "AK-74",
            "visual_faction": None,
        })
        PERSONALITIES = '{"12345": "gruff_but_fair"}'

        LLM_DIALOGUE_RESPONSE = """Always something worth mentioning out there."""

        PUBLISH_REQUEST = json.dumps({
            "topic": "dialogue.display",
            "payload": {
                "speaker_id": "12345",
                "dialogue": "Always something worth mentioning out there.",
                "create_event": True,
            }
        })

        snapshot = await run_lifecycle(
            input_event_json=INPUT_EVENT,
            scene_json=_SCENE,
            characters_alive_json=_EMPTY_ALIVE,
            memory_json=_EMPTY_MEMORY,
            character_json=CHARACTER_RESPONSE,
            llm_responses=[LLM_SPEAKER_RESPONSE, LLM_DIALOGUE_RESPONSE],
            personalities_json=PERSONALITIES,
        )

        # Speaker selection + dialogue generation = 2 LLM calls
        assert len(snapshot.llm_requests) == 2
        assert len(snapshot.published) == 1
        assert snapshot.published[0]["topic"] == "dialogue.display"
        assert snapshot.published[0]["payload"]["speaker_id"] == "12345"
        assert snapshot.published[0]["payload"]["dialogue"] == LLM_DIALOGUE_RESPONSE

        # Speaker selection prompt should include the DIALOGUE event text
        assert_llm_requests(
            snapshot.llm_requests,
            json.dumps([
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["said"]}
                    ],
                    "options": {"temperature": 0.3, "max_tokens": 50}
                },
                {
                    "messages": [
                        {"role": "system", "content_patterns": ["Wolf", "gruff"]},
                        {"role": "user", "content_patterns": ["Barkeep.*said"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestDialogueDescribeEvent:
    """Edge case tests for DIALOGUE describe_event() output."""

    def test_empty_text(self):
        """Empty text string produces empty quoted string."""
        INPUT_EVENT = {
            "type": "DIALOGUE",
            "context": {
                "speaker": {
                    "game_id": 12345,
                    "name": "Wolf",
                    "faction": "stalker",
                    "experience": "Veteran",
                    "reputation": 750
                },
                "text": ""
            },
            "game_time_ms": 0,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = 'Wolf (Veteran, Loner, Reputation: 750) said: ""'

        event = Event.from_dict(INPUT_EVENT)
        result = describe_event(event)
        assert result == EXPECTED_DESCRIPTION

    def test_long_text(self):
        """Long text is preserved in full."""
        long_text = "I've been in the Zone for years and let me tell you something about mutants: they are always hungry, always dangerous, and they never forget."
        INPUT_EVENT = {
            "type": "DIALOGUE",
            "context": {
                "speaker": {
                    "game_id": 12345,
                    "name": "Wolf",
                    "faction": "stalker",
                    "experience": "Veteran",
                    "reputation": 750
                },
                "text": long_text
            },
            "game_time_ms": 0,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = f'Wolf (Veteran, Loner, Reputation: 750) said: "{long_text}"'

        event = Event.from_dict(INPUT_EVENT)
        result = describe_event(event)
        assert result == EXPECTED_DESCRIPTION

    def test_no_speaker(self):
        """Missing speaker context falls back to 'Someone said'."""
        INPUT_EVENT = {
            "type": "DIALOGUE",
            "context": {
                "text": "Hello there"
            },
            "game_time_ms": 0,
            "flags": {}
        }
        EXPECTED_DESCRIPTION = 'Someone said: "Hello there"'

        event = Event.from_dict(INPUT_EVENT)
        result = describe_event(event)
        assert result == EXPECTED_DESCRIPTION
