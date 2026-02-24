"""Integration tests for ANOMALY event handling lifecycle.

ANOMALY is a "junk" event type — still generates dialogue but filtered from
stored memory context in subsequent LLM calls.

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertions |
|------|-----------|----------------|
| test_happy_path | Actor encounters zone_vortex (Vortex), 2 witnesses | Full lifecycle |
| test_known_section | anomaly_type="zone_mine_electric_weak" | resolves to Electro description |
| test_unknown_section | anomaly_type="zone_custom_unknown" | falls back to raw section name |
| test_no_actor | No actor in context | "Someone encountered {resolved}" |
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
    "time": {"Y": 2012, "M": 6, "D": 15, "h": 18, "m": 0, "s": 0, "ms": 0},
    "weather": "rain",
    "emission": False,
    "psy_storm": False,
    "sheltering": False,
    "campfire": None,
    "brain_scorcher_disabled": False,
    "miracle_machine_disabled": False,
})
_EMPTY_MEMORY = json.dumps({"narrative": None, "last_update_time_ms": 0})
_EMPTY_ALIVE = json.dumps({"alive": {}})


class TestAnomalyLifecycle:
    """ANOMALY lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_actor_encounters_vortex(self):
        """Player encounters zone_vortex; 2 witnesses react, Wolf selected."""

        INPUT_EVENT = """
        {
            "event": {
                "type": "ANOMALY",
                "context": {
                    "actor": {
                        "game_id": 0,
                        "name": "Marked One",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 500
                    },
                    "anomaly_type": "zone_vortex"
                },
                "game_time_ms": 5000000,
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

        LLM_DIALOGUE_RESPONSE = """Watch your step — that Vortex nearly had you."""

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
                        {"role": "user", "content_patterns": ["encountered a Vortex anomaly"]}
                    ],
                    "options": {"temperature": 0.3, "max_tokens": 50}
                },
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["encountered a Vortex anomaly"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


class TestAnomalyDescribeEvent:
    """Edge case tests for ANOMALY describe_event() output."""

    def _make_event(self, anomaly_type: str, with_actor: bool = True) -> dict:
        ctx: dict = {"anomaly_type": anomaly_type}
        if with_actor:
            ctx["actor"] = {
                "game_id": 12345, "name": "Wolf", "faction": "stalker",
                "experience": "Veteran", "reputation": 750
            }
        return {"type": "ANOMALY", "context": ctx, "game_time_ms": 0, "flags": {}}

    def test_known_section_vortex(self):
        """Known section resolved to human-readable description."""
        event = Event.from_dict(self._make_event("zone_vortex"))
        result = describe_event(event)
        assert result == "Wolf (Veteran, Loner, Reputation: 750) encountered a Vortex anomaly (gravitational whirlwind pulling objects inward)."

    def test_known_section_electric(self):
        """Known section resolved to Electro description."""
        event = Event.from_dict(self._make_event("zone_mine_electric_weak"))
        result = describe_event(event)
        assert result == "Wolf (Veteran, Loner, Reputation: 750) encountered an Electro anomaly (electrical field discharging lightning)."

    def test_unknown_section_fallback(self):
        """Unknown section falls back to raw section name."""
        event = Event.from_dict(self._make_event("zone_custom_unknown"))
        result = describe_event(event)
        assert result == "Wolf (Veteran, Loner, Reputation: 750) encountered zone_custom_unknown"

    def test_no_actor(self):
        """Missing actor falls back: 'Someone encountered {resolved}'."""
        event = Event.from_dict(self._make_event("zone_mine_electric_weak", with_actor=False))
        result = describe_event(event)
        assert result == "Someone encountered an Electro anomaly (electrical field discharging lightning)."

    def test_empty_anomaly_type(self):
        """Missing/empty anomaly_type falls back to generic 'an anomaly'."""
        event = Event.from_dict(self._make_event("", with_actor=False))
        result = describe_event(event)
        assert result == "Someone encountered an anomaly"
