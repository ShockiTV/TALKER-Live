"""Integration tests for INJURY event handling lifecycle.

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertions |
|------|-----------|----------------|
| test_happy_path | Severe injury, 2 witnesses react | Full lifecycle verification |
| test_severe_injury | severity="severe" | "was injured severely" |
| test_normal_injury | severity="" or absent | "was injured" (no "severely") |
| test_no_actor | No actor context | "Someone was injured" |
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
    "time": {"Y": 2012, "M": 6, "D": 15, "h": 13, "m": 30, "s": 0, "ms": 0},
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


class TestInjuryLifecycle:
    """INJURY lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_severe_injury(self):
        """Player severely injured; 2 witnesses (Wolf + Petruha) react, Wolf selected."""

        INPUT_EVENT = """
        {
            "event": {
                "type": "INJURY",
                "context": {
                    "actor": {
                        "game_id": 0,
                        "name": "Marked One",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 500
                    },
                    "severity": "severe"
                },
                "game_time_ms": 3500000,
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
            "weapon": "AK-74",
            "visual_faction": None,
        })

        LLM_DIALOGUE_RESPONSE = """That's a bad one. Get those wounds patched before they go septic."""

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
                        {"role": "user", "content_patterns": ["injured severely"]}
                    ],
                    "options": {"temperature": 0.3, "max_tokens": 50}
                },
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["injured severely"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


class TestInjuryDescribeEvent:
    """Edge case tests for INJURY describe_event() output."""

    def _make_event(self, severity: str = "", with_actor: bool = True) -> dict:
        ctx: dict = {}
        if severity:
            ctx["severity"] = severity
        if with_actor:
            ctx["actor"] = {
                "game_id": 12345, "name": "Wolf", "faction": "stalker",
                "experience": "Veteran", "reputation": 750
            }
        return {"type": "INJURY", "context": ctx, "game_time_ms": 0, "flags": {}}

    def test_severe_injury(self):
        """severity='severe' adds 'severely' qualifier."""
        event = Event.from_dict(self._make_event("severe"))
        result = describe_event(event)
        assert result == "Wolf (Veteran, Loner, Reputation: 750) was injured severely"

    def test_normal_injury(self):
        """No severity (or non-severe) produces 'was injured' without qualifier."""
        event = Event.from_dict(self._make_event("minor"))
        result = describe_event(event)
        assert result == "Wolf (Veteran, Loner, Reputation: 750) was injured"
        assert "severely" not in result

    def test_no_actor(self):
        """Missing actor falls back to 'Someone was injured'."""
        event = Event.from_dict(self._make_event(with_actor=False))
        result = describe_event(event)
        assert result == "Someone was injured"
