"""Integration tests for RELOAD event handling lifecycle."""

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
    "time": {"Y": 2012, "M": 6, "D": 15, "h": 14, "m": 5, "s": 0, "ms": 0},
    "weather": "clear",
    "emission": False,
    "psy_storm": False,
    "sheltering": False,
    "campfire": None,
    "brain_scorcher_disabled": False,
    "miracle_machine_disabled": False,
})
_EMPTY_MEMORY = json.dumps({"narrative": None, "last_update_time_ms": 0})
_EMPTY_ALIVE = json.dumps({"alive": {}})


class TestReloadLifecycle:
    """RELOAD lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_reload(self):
        """Player reloads weapon; single witness auto-selected reacts."""

        INPUT_EVENT = """
        {
            "event": {
                "type": "RELOAD",
                "context": {
                    "actor": {
                        "game_id": 0,
                        "name": "Marked One",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 500
                    }
                },
                "game_time_ms": 3660000,
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
            "weapon": "AK-74",
            "visual_faction": None,
        })

        LLM_DIALOGUE_RESPONSE = """Stay sharp, we're not done yet."""

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
                        {"role": "user", "content_patterns": ["reloaded"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


class TestReloadDescribeEvent:
    """describe_event() tests for RELOAD."""

    def test_reload_description(self):
        """Reload event is described correctly."""
        event = Event.from_dict({
            "type": "RELOAD",
            "context": {
                "actor": {
                    "game_id": 0, "name": "Marked One", "faction": "stalker",
                    "experience": "Veteran", "reputation": 500
                }
            },
            "game_time_ms": 0,
            "flags": {},
        })
        result = describe_event(event)
        assert "Marked One" in result
        assert "reload" in result.lower()
