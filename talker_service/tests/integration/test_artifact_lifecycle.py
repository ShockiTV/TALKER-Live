"""Integration tests for ARTIFACT event handling lifecycle.

ARTIFACT is a "junk" event type — it still triggers dialogue generation,
but ARTIFACT events in memory context are filtered from LLM prompts.

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertions |
|------|-----------|----------------|
| test_happy_path | Actor finds artifact, 1 witness speaks | Full lifecycle |
| test_action_found | action="found" | "{actor} found {item_name}" |
| test_action_detected | action="detected" | "{actor} detected {item_name}" |
| test_action_picked_up | action="picked_up" | "{actor} picked_up {item_name}" |
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
    "time": {"Y": 2012, "M": 6, "D": 15, "h": 15, "m": 0, "s": 0, "ms": 0},
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


class TestArtifactLifecycle:
    """ARTIFACT lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_actor_finds_artifact(self):
        """Actor (Player) finds a Moonlight; single witness Petruha reacts."""

        INPUT_EVENT = """
        {
            "event": {
                "type": "ARTIFACT",
                "context": {
                    "actor": {
                        "game_id": 0,
                        "name": "Marked One",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 500
                    },
                    "action": "found",
                    "item_name": "Moonlight"
                },
                "game_time_ms": 4000000,
                "witnesses": [
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

        # Single witness — no speaker selection LLM call (Petruha auto-selected)
        CHARACTER_RESPONSE = json.dumps({
            "game_id": 11111,
            "name": "Petruha",
            "faction": "stalker",
            "experience": "Experienced",
            "reputation": 0,
            "personality": "generic.15",
            "backstory": None,
            "weapon": "Shotgun",
            "visual_faction": None,
        })

        LLM_DIALOGUE_RESPONSE = """A Moonlight! That's worth a decent stack of cash at any trader."""

        snapshot = await run_lifecycle(
            input_event_json=INPUT_EVENT,
            scene_json=_SCENE,
            characters_alive_json=_EMPTY_ALIVE,
            memory_json=_EMPTY_MEMORY,
            character_json=CHARACTER_RESPONSE,
            llm_responses=[LLM_DIALOGUE_RESPONSE],
        )

        # Single witness = single LLM call (no speaker selection)
        assert len(snapshot.llm_requests) == 1
        assert len(snapshot.published) == 1
        assert snapshot.published[0]["payload"]["speaker_id"] == "11111"

        assert_llm_requests(
            snapshot.llm_requests,
            json.dumps([
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["found Moonlight"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


class TestArtifactDescribeEvent:
    """Edge case tests for ARTIFACT describe_event() output."""

    def _make_event(self, action: str, item_name: str = "a Moonlight") -> dict:
        return {
            "type": "ARTIFACT",
            "context": {
                "actor": {
                    "game_id": 12345,
                    "name": "Wolf",
                    "faction": "stalker",
                    "experience": "Veteran",
                    "reputation": 750
                },
                "action": action,
                "item_name": item_name
            },
            "game_time_ms": 0,
            "flags": {}
        }

    def test_action_found(self):
        """action='found' produces '{actor} found {item_name}'."""
        event = Event.from_dict(self._make_event("found"))
        result = describe_event(event)
        assert result == "Wolf (Veteran, Loner, Reputation: 750) found a Moonlight"

    def test_action_detected(self):
        """action='detected' uses that verb."""
        event = Event.from_dict(self._make_event("detected"))
        result = describe_event(event)
        assert result == "Wolf (Veteran, Loner, Reputation: 750) detected a Moonlight"

    def test_action_picked_up(self):
        """action='picked_up' uses that verb."""
        event = Event.from_dict(self._make_event("picked_up"))
        result = describe_event(event)
        assert result == "Wolf (Veteran, Loner, Reputation: 750) picked_up a Moonlight"
