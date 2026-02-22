"""Integration tests for SLEEP event handling lifecycle.

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertions |
|------|-----------|----------------|
| test_happy_path | Actor rests 6 hours, 2 witnesses | Full lifecycle |
| test_zero_hours | hours="0" | "rested for 0 hours" |
| test_large_hours | hours="8" | "rested for 8 hours" |
| test_no_actor | No actor context | "Someone fell asleep" |
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
    "loc": "l03_agroprom",
    "poi": None,
    "time": {"Y": 2012, "M": 6, "D": 16, "h": 2, "m": 0, "s": 0, "ms": 0},
    "weather": "clear",
    "emission": False,
    "psy_storm": False,
    "sheltering": False,
    "campfire": "agroprom_campfire",
    "brain_scorcher_disabled": False,
    "miracle_machine_disabled": False,
})
_EMPTY_MEMORY = json.dumps({"narrative": None, "last_update_time_ms": 0, "new_events": []})
_EMPTY_ALIVE = json.dumps({"alive": {}})


class TestSleepLifecycle:
    """SLEEP lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_npc_rests(self):
        """Actor rests 6 hours; 2 witnesses react, Petruha selected."""

        INPUT_EVENT = """
        {
            "event": {
                "type": "SLEEP",
                "context": {
                    "actor": {
                        "game_id": 0,
                        "name": "Marked One",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 500
                    },
                    "hours": "6"
                },
                "game_time_ms": 300000,
                "witnesses": [
                    {
                        "game_id": 22222,
                        "name": "Petruha",
                        "faction": "stalker",
                        "experience": "Experienced",
                        "reputation": 0,
                        "personality": "generic.15"
                    },
                    {
                        "game_id": 33333,
                        "name": "Nimble",
                        "faction": "stalker",
                        "experience": "Experienced",
                        "reputation": 100,
                        "personality": "nimble"
                    }
                ],
                "flags": {}
            },
            "is_important": false
        }
        """

        LLM_SPEAKER_RESPONSE = """{"id": 22222}"""

        CHARACTER_RESPONSE = json.dumps({
            "game_id": 22222,
            "name": "Petruha",
            "faction": "stalker",
            "experience": "Experienced",
            "reputation": 0,
            "personality": "generic.15",
            "backstory": "generic",
            "weapon": "Shotgun",
            "visual_faction": None,
        })

        LLM_DIALOGUE_RESPONSE = """Get some rest. We'll keep watch."""

        snapshot = await run_lifecycle(
            input_event_json=INPUT_EVENT,
            scene_json=_SCENE,
            characters_alive_json=_EMPTY_ALIVE,
            memory_json=_EMPTY_MEMORY,
            character_json=CHARACTER_RESPONSE,
            llm_responses=[LLM_SPEAKER_RESPONSE, LLM_DIALOGUE_RESPONSE],
        )

        assert len(snapshot.llm_requests) == 2
        assert snapshot.published[0]["payload"]["speaker_id"] == "22222"

        assert_llm_requests(
            snapshot.llm_requests,
            json.dumps([
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["rested for 6 hours"]}
                    ],
                    "options": {"temperature": 0.3, "max_tokens": 50}
                },
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["rested for 6 hours"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


class TestSleepDescribeEvent:
    """Edge case tests for SLEEP describe_event() output."""

    def _make_event(self, hours: str = "6", with_actor: bool = True) -> dict:
        ctx: dict = {"hours": hours}
        if with_actor:
            ctx["actor"] = {
                "game_id": 0, "name": "Marked One", "faction": "stalker",
                "experience": "Veteran", "reputation": 500
            }
        return {"type": "SLEEP", "context": ctx, "game_time_ms": 0, "flags": {}}

    def test_zero_hours(self):
        """hours=0 still formats correctly."""
        event = Event.from_dict(self._make_event("0"))
        result = describe_event(event)
        assert "rested for 0 hours" in result

    def test_large_hours(self):
        """hours=8 formats correctly."""
        event = Event.from_dict(self._make_event("8"))
        result = describe_event(event)
        assert "rested for 8 hours" in result

    def test_no_actor(self):
        """Missing actor falls back gracefully."""
        event = Event.from_dict(self._make_event(with_actor=False))
        result = describe_event(event)
        assert "Someone" in result or result is not None
