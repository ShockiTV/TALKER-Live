"""Integration tests for IDLE event handling lifecycle."""

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
    "time": {"Y": 2012, "M": 6, "D": 15, "h": 12, "m": 0, "s": 0, "ms": 0},
    "weather": "overcast",
    "emission": False,
    "psy_storm": False,
    "sheltering": False,
    "campfire": "escape_campfire",
    "brain_scorcher_disabled": False,
    "miracle_machine_disabled": False,
})
_EMPTY_MEMORY = json.dumps({"narrative": None, "last_update_time_ms": 0})
_EMPTY_ALIVE = json.dumps({"alive": {}})


class TestIdleLifecycle:
    """IDLE lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_idle_npc(self):
        """NPC is idle nearby; single witness auto-selected reacts/initiates conversation."""

        INPUT_EVENT = """
        {
            "event": {
                "type": "IDLE",
                "context": {
                    "actor": {
                        "game_id": 12345,
                        "name": "Wolf",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 750
                    }
                },
                "game_time_ms": 43200000,
                "witnesses": [
                    {
                        "game_id": 12345,
                        "name": "Wolf",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 750,
                        "personality": "gruff_but_fair"
                    }
                ],
                "flags": {}
            },
            "is_important": false
        }
        """

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

        LLM_DIALOGUE_RESPONSE = """You new around here? Don't get comfortable — the Zone has a way of surprising you."""

        snapshot = await run_lifecycle(
            input_event_json=INPUT_EVENT,
            scene_json=_SCENE,
            characters_alive_json=_EMPTY_ALIVE,
            memory_json=_EMPTY_MEMORY,
            character_json=CHARACTER_RESPONSE,
            llm_responses=[LLM_DIALOGUE_RESPONSE],
        )

        # Single witness → auto-selected, only 1 LLM call (dialogue)
        assert len(snapshot.llm_requests) == 1
        assert snapshot.published[0]["payload"]["speaker_id"] == "12345"

        assert_llm_requests(
            snapshot.llm_requests,
            json.dumps([
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["nearby", "available"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


class TestIdleDescribeEvent:
    """describe_event() tests for IDLE."""

    def test_idle_description(self):
        """Idle event description includes actor name and availability."""
        event = Event.from_dict({
            "type": "IDLE",
            "context": {
                "actor": {
                    "game_id": 12345, "name": "Wolf", "faction": "stalker",
                    "experience": "Veteran", "reputation": 750
                }
            },
            "game_time_ms": 0,
            "flags": {},
        })
        result = describe_event(event)
        assert "Wolf" in result
        assert "nearby" in result.lower() or "available" in result.lower() or "idle" in result.lower()
