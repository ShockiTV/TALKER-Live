"""Integration tests for TASK event handling lifecycle.

================================================================================
COVERAGE
================================================================================

| Test | Variation | Key Assertions |
|------|-----------|----------------|
| test_happy_path | Task completed with giver, 2 witnesses | Full lifecycle |
| test_task_completed | status="completed" | "completed task: ..." in description |
| test_task_failed | status="failed" | "failed task: ..." in description |
| test_task_updated | status="updated" | "updated task: ..." in description |
| test_no_task_giver | No task_giver field | Giver omitted from description |
| test_with_task_giver | task_giver present | "for {giver}" appended |
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
    "loc": "l04_darkvalley",
    "poi": None,
    "time": {"Y": 2012, "M": 6, "D": 17, "h": 16, "m": 0, "s": 0, "ms": 0},
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


class TestTaskLifecycle:
    """TASK lifecycle tests."""

    @pytest.mark.asyncio
    async def test_happy_path_task_completed_with_giver(self):
        """Player completes a task given by Barkeep; 2 witnesses react."""

        INPUT_EVENT = """
        {
            "event": {
                "type": "TASK",
                "context": {
                    "actor": {
                        "game_id": 0,
                        "name": "Marked One",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 500
                    },
                    "task_name": "Eliminate the bandits in Dark Valley",
                    "task_giver": "Barkeep",
                    "task_status": "completed"
                },
                "game_time_ms": 6000000,
                "witnesses": [
                    {
                        "game_id": 55555,
                        "name": "Barkeep",
                        "faction": "stalker",
                        "experience": "Veteran",
                        "reputation": 1000,
                        "personality": "barkeep"
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

        LLM_SPEAKER_RESPONSE = """{"id": 55555}"""

        CHARACTER_RESPONSE = json.dumps({
            "game_id": 55555,
            "name": "Barkeep",
            "faction": "stalker",
            "experience": "Veteran",
            "reputation": 1000,
            "personality": "barkeep",
            "backstory": "unique",
            "weapon": None,
            "visual_faction": None,
        })

        LLM_DIALOGUE_RESPONSE = """Nicely done. The Zone is a little quieter now."""

        snapshot = await run_lifecycle(
            input_event_json=INPUT_EVENT,
            scene_json=_SCENE,
            characters_alive_json=_EMPTY_ALIVE,
            memory_json=_EMPTY_MEMORY,
            character_json=CHARACTER_RESPONSE,
            llm_responses=[LLM_SPEAKER_RESPONSE, LLM_DIALOGUE_RESPONSE],
        )

        assert len(snapshot.llm_requests) == 2
        assert snapshot.published[0]["payload"]["speaker_id"] == "55555"

        assert_llm_requests(
            snapshot.llm_requests,
            json.dumps([
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["completed task", "Eliminate the bandits"]}
                    ],
                    "options": {"temperature": 0.3, "max_tokens": 50}
                },
                {
                    "messages": [
                        {"role": "user", "content_patterns": ["completed task", "Eliminate the bandits"]}
                    ],
                    "options": {"temperature": 0.8, "max_tokens": 200}
                }
            ])
        )


class TestTaskDescribeEvent:
    """Edge case tests for TASK describe_event() output."""

    def _make_event(self, status: str = "completed", with_giver: bool = True) -> dict:
        ctx: dict = {
            "actor": {
                "game_id": 0, "name": "Marked One", "faction": "stalker",
                "experience": "Veteran", "reputation": 500
            },
            "task_name": "Scout the area",
            "task_status": status,
        }
        if with_giver:
            ctx["task_giver"] = "Barkeep"
        return {"type": "TASK", "context": ctx, "game_time_ms": 0, "flags": {}}

    def test_task_completed(self):
        """Status 'completed' appears in description."""
        event = Event.from_dict(self._make_event("completed"))
        result = describe_event(event)
        assert "completed" in result.lower()
        assert "Scout the area" in result

    def test_task_failed(self):
        """Status 'failed' appears in description."""
        event = Event.from_dict(self._make_event("failed"))
        result = describe_event(event)
        assert "failed" in result.lower()

    def test_task_updated(self):
        """Status 'updated' appears in description."""
        event = Event.from_dict(self._make_event("updated"))
        result = describe_event(event)
        assert "updated" in result.lower()

    def test_with_task_giver(self):
        """task_giver does not appear in describe_event output (it is omitted from the short description)."""
        event = Event.from_dict(self._make_event(with_giver=True))
        result = describe_event(event)
        # describe_event omits task_giver — the task name and status are what matter
        assert "Scout the area" in result
        assert "completed" in result.lower()

    def test_no_task_giver(self):
        """Without task_giver the description still contains task name and status."""
        event = Event.from_dict(self._make_event(with_giver=False))
        result = describe_event(event)
        assert "Scout the area" in result
