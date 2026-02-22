"""Integration tests for WEAPON_JAM event handling lifecycle."""

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
    "time": {"Y": 2012, "M": 6, "D": 15, "h": 14, "m": 0, "s": 0, "ms": 0},
    "weather": "clear",
    "emission": False,
    "psy_storm": False,
    "sheltering": False,
    "campfire": None,
    "brain_scorcher_disabled": False,
    "miracle_machine_disabled": False,
})
_EMPTY_MEMORY = json.dumps({"narrative": None, "last_update_time_ms": 0, "new_events": []})
_EMPTY_ALIVE = json.dumps({"alive": {}})


class TestWeaponJamLifecycle:
    """WEAPON_JAM lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_weapon_jams(self):
        """Weapon jams during combat; single witness auto-selected reacts."""

        INPUT_EVENT = """
        {
            "event": {
                "type": "WEAPON_JAM",
                "context": {
                    "actor": {
                        "game_id": 0,
                        "name": "Marked One",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 500
                    }
                },
                "game_time_ms": 3600000,
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

        LLM_DIALOGUE_RESPONSE = """Should've cleaned that thing last night."""

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
                        {"role": "user", "content_patterns": ["weapon jammed"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


class TestWeaponJamDescribeEvent:
    """describe_event() tests for WEAPON_JAM."""

    def test_weapon_jam_description(self):
        """Actor's weapon jam is described correctly."""
        event = Event.from_dict({
            "type": "WEAPON_JAM",
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
        assert "jammed" in result.lower() or "jam" in result.lower()
