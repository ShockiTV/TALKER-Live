# Trigger-and-Event-Linking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan.

**Goal:** Wire `ts` timestamps through the event pipeline so picker and dialogue steps reference events by `[ts]` pointers, with a unified deduplicated event list fetched for all candidates before the picker step.

**Architecture:** New `event_list.py` module handles dedup/format/filter of events from all candidates. `handle_event()` fetches events for all candidates in one batch before the picker. Picker and dialogue user messages use `[ts]` pointer format with witness annotations. Dialogue user messages become ephemeral (removed after LLM call; only assistant response persists).

**Tech Stack:** Python 3.10+, pytest, unittest.mock (AsyncMock/MagicMock), existing BatchQuery/StateQueryClient APIs

---

## Spec Coverage Map

| Scenario | Spec Source | Task |
|----------|-------------|------|
| Batch query for 4 candidates | specs/event-list-assembly/spec.md | Task 4 |
| Candidate with no stored events | specs/event-list-assembly/spec.md | Task 4 |
| Batch query timeout | specs/event-list-assembly/spec.md | Task 4 |
| Same event witnessed by 3 candidates | specs/event-list-assembly/spec.md | Task 1 |
| Events unique to one candidate | specs/event-list-assembly/spec.md | Task 1 |
| Death event with two witnesses | specs/event-list-assembly/spec.md | Task 2 |
| Event with one witness | specs/event-list-assembly/spec.md | Task 2 |
| Three events sorted by timestamp | specs/event-list-assembly/spec.md | Task 2 |
| Speaker witnessed 2 of 5 events | specs/event-list-assembly/spec.md | Task 3 |
| Publish death event with ts included | specs/lua-event-publisher/spec.md | N/A (already tested) |
| ts is the unique timestamp from event creation | specs/lua-event-publisher/spec.md | N/A (already tested) |
| Serialize event includes ts | specs/lua-event-publisher/spec.md | N/A (already tested) |
| Building the picker prompt for an event | specs/pointer-based-dialogue-messages/spec.md | Task 5 |
| Picker message does not inline event description separately | specs/pointer-based-dialogue-messages/spec.md | Task 5 |
| Building the dialogue prompt for the chosen speaker | specs/pointer-based-dialogue-messages/spec.md | Task 6 |
| Speaker has no personal narrative memories yet | specs/pointer-based-dialogue-messages/spec.md | Task 6 |
| LLM processes the full message array | specs/pointer-based-dialogue-messages/spec.md | Task 7 |
| Picker step — all candidates' events (union) | specs/witness-event-injection/spec.md | Task 5 |
| Dialogue step — speaker-filtered events | specs/witness-event-injection/spec.md | Task 6 |
| Events not in context block | specs/witness-event-injection/spec.md | Task 6 |
| Dialogue user message is ephemeral | specs/witness-event-injection/spec.md | Task 6 |
| Filter events for a specific speaker | specs/witness-event-injection/spec.md | Task 3 |
| Events batch precedes picker | specs/witness-event-injection/spec.md | Task 4 |
| Triggering event has ts in payload | specs/witness-event-injection/spec.md | N/A (already tested) |

---

- [x] Task 1: assemble_event_list dedup + witness map
- [x] Task 2: format_event_line + build_event_list_text
- [x] Task 3: filter_events_for_speaker (name-based)
- [x] Task 4: Batch fetch events for all candidates before picker
- [x] Task 5: Picker with event list + [ts] pointers
- [x] Task 6: Dialogue with ephemeral user message + event list
- [x] Task 7: Update prompt builders + full flow integration test
- [x] Task 8: Clean up stale code + final verification

---

### Task 1: assemble_event_list dedup + witness map

**Files:**
- Create: `talker_service/src/talker_service/dialogue/event_list.py`
- Test: `talker_service/tests/test_event_list.py`

**Step 1: Write the failing tests**

```python
# talker_service/tests/test_event_list.py
"""Tests for event list assembly, formatting, and filtering."""

import pytest

from talker_service.dialogue.event_list import assemble_event_list


class TestAssembleEventList:
    """Tests for assemble_event_list() dedup + witness map."""

    def test_same_event_witnessed_by_3_candidates(self):
        """Scenario: Same event witnessed by 3 candidates."""
        events_by_candidate = {
            "npc_1": [{"ts": 1709912345, "type": "death", "context": {"actor": {"name": "Wolf"}, "victim": {"name": "Bandit"}}}],
            "npc_2": [{"ts": 1709912345, "type": "death", "context": {"actor": {"name": "Wolf"}, "victim": {"name": "Bandit"}}}],
            "npc_3": [{"ts": 1709912345, "type": "death", "context": {"actor": {"name": "Wolf"}, "victim": {"name": "Bandit"}}}],
        }
        candidate_names = {"npc_1": "Echo", "npc_2": "Wolf", "npc_3": "Fanatic"}

        unique_events, witness_map = assemble_event_list(events_by_candidate, candidate_names)

        assert len(unique_events) == 1
        assert 1709912345 in unique_events
        assert witness_map[1709912345] == {"Echo", "Wolf", "Fanatic"}

    def test_events_unique_to_one_candidate(self):
        """Scenario: Events unique to one candidate."""
        events_by_candidate = {
            "npc_1": [
                {"ts": 1709912001, "type": "callout", "context": {"actor": {"name": "Echo"}}},
                {"ts": 1709912345, "type": "death", "context": {"actor": {"name": "Wolf"}, "victim": {"name": "Bandit"}}},
            ],
            "npc_2": [
                {"ts": 1709912345, "type": "death", "context": {"actor": {"name": "Wolf"}, "victim": {"name": "Bandit"}}},
            ],
        }
        candidate_names = {"npc_1": "Echo", "npc_2": "Wolf"}

        unique_events, witness_map = assemble_event_list(events_by_candidate, candidate_names)

        assert len(unique_events) == 2
        assert 1709912001 in unique_events
        assert witness_map[1709912001] == {"Echo"}
        assert witness_map[1709912345] == {"Echo", "Wolf"}

    def test_empty_events(self):
        """All candidates have empty event lists."""
        events_by_candidate = {"npc_1": [], "npc_2": []}
        candidate_names = {"npc_1": "Echo", "npc_2": "Wolf"}

        unique_events, witness_map = assemble_event_list(events_by_candidate, candidate_names)

        assert len(unique_events) == 0
        assert len(witness_map) == 0

    def test_events_without_ts_are_skipped(self):
        """Events lacking ts field are skipped."""
        events_by_candidate = {
            "npc_1": [{"type": "idle", "context": {}}],  # no ts
        }
        candidate_names = {"npc_1": "Echo"}

        unique_events, witness_map = assemble_event_list(events_by_candidate, candidate_names)

        assert len(unique_events) == 0
```

**Step 2: Run tests to verify they fail**

Run: `talker-tests MCP run_tests { pattern: "test_event_list" }`
Expected: FAIL — `ModuleNotFoundError: No module named 'talker_service.dialogue.event_list'`

**Step 3: Write minimal implementation**

```python
# talker_service/src/talker_service/dialogue/event_list.py
"""Event list assembly: dedup, format, and filter events across candidates.

Fetches witness events for all speaker candidates, deduplicates by `ts`
timestamp, and provides formatting/filtering for picker and dialogue steps.
"""

from __future__ import annotations

from typing import Any


def assemble_event_list(
    events_by_candidate: dict[str, list[dict[str, Any]]],
    candidate_names: dict[str, str],
) -> tuple[dict[int, dict[str, Any]], dict[int, set[str]]]:
    """Deduplicate events across candidates by ts.

    Returns:
        unique_events: {ts: event_dict} — deduplicated, keyed by ts
        witness_map: {ts: {name1, name2, ...}} — which candidates saw it
    """
    unique_events: dict[int, dict[str, Any]] = {}
    witness_map: dict[int, set[str]] = {}

    for cand_id, events in events_by_candidate.items():
        cand_name = candidate_names.get(cand_id, cand_id)
        for event in events:
            ts = event.get("ts")
            if ts is None:
                continue
            ts = int(ts)
            if ts not in unique_events:
                unique_events[ts] = event
            if ts not in witness_map:
                witness_map[ts] = set()
            witness_map[ts].add(cand_name)

    return unique_events, witness_map
```

**Step 4: Run tests to verify they pass**

Run: `talker-tests MCP run_tests { pattern: "test_event_list" }`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add talker_service/src/talker_service/dialogue/event_list.py talker_service/tests/test_event_list.py
git commit -m "feat: add assemble_event_list for dedup + witness map"
```

---

### Task 2: format_event_line + build_event_list_text

**Files:**
- Modify: `talker_service/src/talker_service/dialogue/event_list.py`
- Modify: `talker_service/tests/test_event_list.py`

**Step 1: Write the failing tests**

Append to `talker_service/tests/test_event_list.py`:

```python
from talker_service.dialogue.event_list import format_event_line, build_event_list_text


class TestFormatEventLine:
    """Tests for format_event_line()."""

    def test_death_event_two_witnesses(self):
        """Scenario: Death event with two witnesses."""
        event = {"type": "death", "context": {"actor": {"name": "Freedom Soldier"}, "victim": {"name": "Monolith Fighter"}}}
        result = format_event_line(1709912001, event, {"Echo", "Wolf"})
        assert result.startswith("[1709912001]")
        assert "DEATH" in result
        assert "Freedom Soldier" in result
        assert "killed" in result
        assert "Monolith Fighter" in result
        # Witness names — order may vary so check both are present
        assert "Echo" in result
        assert "Wolf" in result
        assert "witnesses:" in result

    def test_event_one_witness(self):
        """Scenario: Event with one witness."""
        event = {"type": "callout", "context": {"actor": {"name": "Duty Soldier"}}}
        result = format_event_line(1709912078, event, {"Echo"})
        assert "[1709912078]" in result
        assert "CALLOUT" in result
        assert "(witnesses: Echo)" in result

    def test_injury_event_uses_injured_verb(self):
        event = {"type": "injury", "context": {"actor": {"name": "Snork"}, "victim": {"name": "Loner"}}}
        result = format_event_line(100, event, {"Wolf"})
        assert "injured" in result

    def test_event_actor_only(self):
        """Event with actor but no victim."""
        event = {"type": "emission", "context": {"actor": {"name": "Zone"}}}
        result = format_event_line(200, event, {"Echo"})
        assert "Zone" in result
        assert "EMISSION" in result

    def test_event_no_actor_no_victim(self):
        """Event with no actor/victim context."""
        event = {"type": "idle", "context": {}}
        result = format_event_line(300, event, {"Echo"})
        assert "[300]" in result
        assert "IDLE" in result


class TestBuildEventListText:
    """Tests for build_event_list_text()."""

    def test_three_events_sorted_by_ts(self):
        """Scenario: Three events sorted by timestamp ascending."""
        unique_events = {
            1709912345: {"type": "death", "context": {"actor": {"name": "A"}, "victim": {"name": "B"}}},
            1709912001: {"type": "callout", "context": {"actor": {"name": "C"}}},
            1709912078: {"type": "injury", "context": {"actor": {"name": "D"}, "victim": {"name": "E"}}},
        }
        witness_map = {
            1709912345: {"Echo", "Wolf"},
            1709912001: {"Echo"},
            1709912078: {"Wolf"},
        }
        text = build_event_list_text(unique_events, witness_map)
        lines = text.strip().split("\n")
        assert len(lines) == 3
        # Verify ascending ts order
        assert lines[0].startswith("[1709912001]")
        assert lines[1].startswith("[1709912078]")
        assert lines[2].startswith("[1709912345]")

    def test_empty_events_returns_empty_string(self):
        text = build_event_list_text({}, {})
        assert text == ""
```

**Step 2: Run tests to verify they fail**

Run: `talker-tests MCP run_tests { pattern: "test_event_list" }`
Expected: FAIL — `ImportError: cannot import name 'format_event_line'`

**Step 3: Write minimal implementation**

Append to `talker_service/src/talker_service/dialogue/event_list.py`:

```python
# Verb mapping for event descriptions
_VERB_MAP: dict[str, str] = {
    "DEATH": "killed",
    "INJURY": "injured",
}

# Event type display name mapping
_EVENT_DISPLAY_NAMES: dict[str | int, str] = {
    "death": "DEATH", "dialogue": "DIALOGUE", "callout": "CALLOUT",
    "taunt": "TAUNT", "artifact": "ARTIFACT", "anomaly": "ANOMALY",
    "map_transition": "MAP_TRANSITION", "emission": "EMISSION",
    "injury": "INJURY", "sleep": "SLEEP", "task": "TASK",
    "weapon_jam": "WEAPON_JAM", "reload": "RELOAD", "idle": "IDLE",
    "action": "ACTION",
    0: "DEATH", 1: "DIALOGUE", 2: "CALLOUT", 3: "TAUNT",
    4: "ARTIFACT", 5: "ANOMALY", 6: "MAP_TRANSITION", 7: "EMISSION",
    8: "INJURY", 9: "SLEEP", 10: "TASK", 11: "WEAPON_JAM",
    12: "RELOAD", 13: "IDLE", 14: "ACTION",
}


def _resolve_display_name(event_type: str | int) -> str:
    return _EVENT_DISPLAY_NAMES.get(
        event_type,
        event_type.upper() if isinstance(event_type, str) else f"EVENT_{event_type}",
    )


def format_event_line(ts: int, event: dict[str, Any], witness_names: set[str]) -> str:
    """Format: [ts] TYPE — actor verb victim (witnesses: Name1, Name2)"""
    event_type = event.get("type", "unknown")
    event_name = _resolve_display_name(event_type)

    context = event.get("context", {})
    actor = context.get("actor") or context.get("killer")
    victim = context.get("victim")

    actor_name = actor.get("name", "Unknown") if isinstance(actor, dict) else str(actor) if actor else None
    victim_name = victim.get("name", "Unknown") if isinstance(victim, dict) else str(victim) if victim else None

    witnesses_str = ", ".join(sorted(witness_names))

    if actor_name and victim_name:
        verb = _VERB_MAP.get(event_name, "affected")
        return f"[{ts}] {event_name} — {actor_name} {verb} {victim_name} (witnesses: {witnesses_str})"
    elif actor_name:
        return f"[{ts}] {event_name} — {actor_name} (witnesses: {witnesses_str})"
    else:
        return f"[{ts}] {event_name} (witnesses: {witnesses_str})"


def build_event_list_text(
    unique_events: dict[int, dict[str, Any]],
    witness_map: dict[int, set[str]],
) -> str:
    """Build multi-line text block sorted by ts ascending."""
    if not unique_events:
        return ""
    lines = []
    for ts in sorted(unique_events.keys()):
        event = unique_events[ts]
        witnesses = witness_map.get(ts, set())
        lines.append(format_event_line(ts, event, witnesses))
    return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `talker-tests MCP run_tests { pattern: "test_event_list" }`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add talker_service/src/talker_service/dialogue/event_list.py talker_service/tests/test_event_list.py
git commit -m "feat: add format_event_line and build_event_list_text"
```

---

### Task 3: filter_events_for_speaker (name-based)

**Files:**
- Modify: `talker_service/src/talker_service/dialogue/event_list.py`
- Modify: `talker_service/tests/test_event_list.py`

**Step 1: Write the failing tests**

Append to `talker_service/tests/test_event_list.py`:

```python
from talker_service.dialogue.event_list import filter_events_for_speaker


class TestFilterEventsForSpeaker:
    """Tests for filter_events_for_speaker()."""

    def test_speaker_witnessed_2_of_5(self):
        """Scenario: Speaker witnessed 2 of 5 events."""
        unique_events = {
            100: {"type": "death", "context": {}},
            200: {"type": "callout", "context": {}},
            300: {"type": "injury", "context": {}},
            400: {"type": "idle", "context": {}},
            500: {"type": "taunt", "context": {}},
        }
        witness_map = {
            100: {"Echo", "Wolf"},
            200: {"Wolf"},
            300: {"Echo", "Fanatic"},
            400: {"Wolf", "Fanatic"},
            500: {"Fanatic"},
        }

        filtered_events, filtered_witness = filter_events_for_speaker(
            unique_events, witness_map, "Echo",
        )

        assert len(filtered_events) == 2
        assert 100 in filtered_events
        assert 300 in filtered_events
        # Witness annotations should still include all witnesses
        assert filtered_witness[100] == {"Echo", "Wolf"}
        assert filtered_witness[300] == {"Echo", "Fanatic"}

    def test_speaker_witnessed_no_events(self):
        unique_events = {100: {"type": "death", "context": {}}}
        witness_map = {100: {"Wolf"}}
        filtered_events, filtered_witness = filter_events_for_speaker(
            unique_events, witness_map, "Echo",
        )
        assert len(filtered_events) == 0

    def test_empty_events(self):
        filtered_events, filtered_witness = filter_events_for_speaker({}, {}, "Echo")
        assert len(filtered_events) == 0
```

**Step 2: Run tests to verify they fail**

Run: `talker-tests MCP run_tests { pattern: "test_event_list" }`
Expected: FAIL — `ImportError: cannot import name 'filter_events_for_speaker'`

**Step 3: Write minimal implementation**

Append to `talker_service/src/talker_service/dialogue/event_list.py`:

```python
def filter_events_for_speaker(
    unique_events: dict[int, dict[str, Any]],
    witness_map: dict[int, set[str]],
    speaker_name: str,
) -> tuple[dict[int, dict[str, Any]], dict[int, set[str]]]:
    """Filter events to only those witnessed by the given speaker.

    Witness annotations are preserved in full (not just the speaker).

    Returns:
        filtered_events: {ts: event_dict} for events where speaker is a witness
        filtered_witness: {ts: set[str]} with full witness sets
    """
    filtered_events: dict[int, dict[str, Any]] = {}
    filtered_witness: dict[int, set[str]] = {}

    for ts, witnesses in witness_map.items():
        if speaker_name in witnesses:
            filtered_events[ts] = unique_events[ts]
            filtered_witness[ts] = witnesses

    return filtered_events, filtered_witness
```

**Step 4: Run tests to verify they pass**

Run: `talker-tests MCP run_tests { pattern: "test_event_list" }`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add talker_service/src/talker_service/dialogue/event_list.py talker_service/tests/test_event_list.py
git commit -m "feat: add filter_events_for_speaker name-based filter"
```

---

### Task 4: Batch fetch events for all candidates before picker

**Files:**
- Modify: `talker_service/src/talker_service/dialogue/conversation.py`
- Modify: `talker_service/tests/test_conversation.py`

This changes `handle_event()` to fetch witness events for ALL candidates in one batch BEFORE the picker step, instead of fetching only for the chosen speaker after the picker.

**Step 1: Write the failing tests**

Append to `talker_service/tests/test_conversation.py`:

```python
class TestBatchEventFetch:
    """Tests for fetching events for all candidates before picker."""

    @pytest.mark.asyncio
    async def test_batch_query_for_4_candidates(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: Batch query for 4 candidates fetches events before picker."""
        candidates = [
            {"game_id": f"npc_{i}", "name": f"NPC{i}", "faction": "loner", "background": None}
            for i in range(1, 5)
        ]
        event = {"type": "death", "ts": 9999, "context": {}}

        call_count = 0
        async def _complete(messages, opts=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return "npc_1"  # picker
            return "Dialogue text."  # dialogue

        mock_llm_client.complete = AsyncMock(side_effect=_complete)

        # Track execute_batch calls to verify events batch comes before picker
        batch_calls = []
        async def _track_batch(batch, **kw):
            query_ids = list(batch.build()[0].keys()) if hasattr(batch, 'build') else []
            batch_calls.append(batch)
            # Return appropriate results
            result_data = {}
            for q in batch.query_ids:
                if q.startswith("events_"):
                    result_data[q] = {"ok": True, "data": []}
                elif q == "scene":
                    result_data[q] = {"ok": True, "data": {"loc": "l01_escape", "weather": "clear", "time": {"h": 14, "m": 35}, "emission": False, "psy_storm": False, "sheltering": False, "campfire": None, "brain_scorcher_disabled": False, "miracle_machine_disabled": False}}
                elif q == "alive":
                    result_data[q] = {"ok": True, "data": {}}
                else:
                    result_data[q] = {"ok": True, "data": []}
            return BatchResult(result_data)

        mock_state_client.execute_batch = AsyncMock(side_effect=_track_batch)

        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        await manager.handle_event(event, candidates, "", {})

        # Find the events batch — should have 4 events_npc_X queries
        events_batch = None
        for b in batch_calls:
            ids = b.query_ids
            if any(qid.startswith("events_") for qid in ids):
                events_batch = b
                break
        assert events_batch is not None, "No events batch query was issued"
        event_query_ids = [q for q in events_batch.query_ids if q.startswith("events_")]
        assert len(event_query_ids) == 4

    @pytest.mark.asyncio
    async def test_candidate_with_no_events(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: Candidate with no stored events gets empty list."""
        candidates = [
            {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None},
            {"game_id": "npc_2", "name": "Wolf", "faction": "loner", "background": None},
        ]
        event = {"type": "death", "ts": 9999, "context": {}}

        mock_llm_client.complete = AsyncMock(side_effect=["npc_1", "Dialogue."])

        # npc_1 has events, npc_2 has empty
        async def _batch(batch, **kw):
            result_data = {}
            for q in batch.query_ids:
                if q == "events_npc_1":
                    result_data[q] = {"ok": True, "data": [{"ts": 100, "type": "callout", "context": {}}]}
                elif q == "events_npc_2":
                    result_data[q] = {"ok": True, "data": []}
                elif q == "scene":
                    result_data[q] = {"ok": True, "data": {"loc": "l01_escape", "weather": "clear", "time": {"h": 14, "m": 35}, "emission": False, "psy_storm": False, "sheltering": False, "campfire": None, "brain_scorcher_disabled": False, "miracle_machine_disabled": False}}
                elif q == "alive":
                    result_data[q] = {"ok": True, "data": {}}
                else:
                    result_data[q] = {"ok": True, "data": []}
            return BatchResult(result_data)

        mock_state_client.execute_batch = AsyncMock(side_effect=_batch)

        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        # Should succeed without error
        speaker_id, dialogue = await manager.handle_event(event, candidates, "", {})
        assert speaker_id == "npc_1"
        assert dialogue == "Dialogue."

    @pytest.mark.asyncio
    async def test_batch_query_timeout_proceeds_with_empty(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: Batch query timeout proceeds with empty event lists."""
        candidates = [
            {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None},
        ]
        event = {"type": "idle", "ts": 9999, "context": {}}

        mock_llm_client.complete = AsyncMock(return_value="Some words.")

        call_idx = 0
        async def _batch(batch, **kw):
            nonlocal call_idx
            call_idx += 1
            ids = batch.query_ids
            if any(q.startswith("events_") for q in ids):
                raise TimeoutError("batch timeout")
            result_data = {}
            for q in ids:
                if q == "scene":
                    result_data[q] = {"ok": True, "data": {"loc": "l01_escape", "weather": "clear", "time": {"h": 14, "m": 35}, "emission": False, "psy_storm": False, "sheltering": False, "campfire": None, "brain_scorcher_disabled": False, "miracle_machine_disabled": False}}
                elif q == "alive":
                    result_data[q] = {"ok": True, "data": {}}
                else:
                    result_data[q] = {"ok": True, "data": []}
            return BatchResult(result_data)

        mock_state_client.execute_batch = AsyncMock(side_effect=_batch)

        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        # Should not raise — proceeds with empty events
        speaker_id, dialogue = await manager.handle_event(event, candidates, "", {})
        assert dialogue == "Some words."
```

**Step 2: Run tests to verify they fail**

Run: `talker-tests MCP run_tests { pattern: "TestBatchEventFetch" }`
Expected: FAIL — test expects events batch query with `events_npc_X` IDs, but current code only fetches for chosen speaker after picker

**Step 3: Modify handle_event to fetch events before picker**

In `talker_service/src/talker_service/dialogue/conversation.py`, in `handle_event()`:

1. Add import at top: `from .event_list import assemble_event_list, build_event_list_text, filter_events_for_speaker as filter_events_by_name`
2. Move event fetching before the picker step:

Replace the current post-picker event fetch block:
```python
        # Fetch witness events for the chosen speaker
        witness_events: list[dict[str, Any]] = []
        try:
            ev_batch = (
                BatchQuery()
                .add("events", "query.memory.events",
                     params={"character_id": speaker_id})
            )
            ev_result = await self.state_client.execute_batch(ev_batch, timeout=10.0)
            if ev_result.ok("events"):
                raw_events = ev_result["events"]
                if isinstance(raw_events, list):
                    witness_events = raw_events
        except Exception as e:
            logger.warning(f"Failed to fetch witness events for {speaker_id}: {e}")
```

With a pre-picker batch fetch for all candidates + event list assembly:

```python
        # Fetch witness events for ALL candidates before picker
        events_by_candidate: dict[str, list[dict[str, Any]]] = {}
        candidate_names: dict[str, str] = {}
        for cand in candidates:
            cid = str(cand.get("game_id", ""))
            candidate_names[cid] = cand.get("name", "Unknown")

        try:
            ev_batch = BatchQuery()
            for cid in candidate_names:
                ev_batch.add(f"events_{cid}", "query.memory.events",
                             params={"character_id": cid})
            ev_result = await self.state_client.execute_batch(ev_batch, timeout=10.0)
            for cid in candidate_names:
                qid = f"events_{cid}"
                if ev_result.ok(qid):
                    raw = ev_result[qid]
                    events_by_candidate[cid] = raw if isinstance(raw, list) else []
                else:
                    events_by_candidate[cid] = []
        except Exception as e:
            logger.warning(f"Failed to fetch candidate events: {e}")
            for cid in candidate_names:
                events_by_candidate[cid] = []

        # Assemble unified event list
        unique_events, witness_map = assemble_event_list(events_by_candidate, candidate_names)
        event_list_text = build_event_list_text(unique_events, witness_map)
```

Move this block to BEFORE the `# Step 1: Speaker picker` comment.

Then pass `event_list_text` and the event data to the picker and dialogue steps (wired in Tasks 5-6).

Also remove the old post-picker single-speaker event fetch.

**Step 4: Run tests to verify they pass**

Run: `talker-tests MCP run_tests { pattern: "TestBatchEventFetch" }`
Expected: PASS

**Step 5: Commit**

```bash
git add talker_service/src/talker_service/dialogue/conversation.py talker_service/tests/test_conversation.py
git commit -m "feat: batch fetch events for all candidates before picker"
```

---

### Task 5: Picker with event list + [ts] pointers

**Files:**
- Modify: `talker_service/src/talker_service/dialogue/conversation.py` — `_run_speaker_picker()`
- Modify: `talker_service/tests/test_conversation.py`

**Step 1: Write the failing tests**

Update existing `TestPickerPointerFormat` and add new tests in `talker_service/tests/test_conversation.py`:

```python
class TestPickerWithEventList:
    """Tests for picker step with unified event list + [ts] pointers."""

    @pytest.mark.asyncio
    async def test_picker_includes_event_list(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Scenario: Picker prompt includes Recent events section with [ts] format."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        candidates = [
            {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None},
            {"game_id": "npc_2", "name": "Wolf", "faction": "loner", "background": None},
        ]
        event = {"type": "death", "ts": 1709912345, "context": {"actor": {"name": "Duty"}, "victim": {"name": "Freedom"}}}
        event_list_text = "[1709912001] CALLOUT — Echo (witnesses: Echo)\n[1709912345] DEATH — Duty killed Freedom (witnesses: Echo, Wolf)"

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "npc_1"
        mock_llm_client.complete = _capture

        await manager._run_speaker_picker(candidates, event, mock_llm_client, event_list_text=event_list_text)

        picker_msg = captured[0][-1]
        assert "**Recent events in area:**" in picker_msg.content
        assert "[1709912345]" in picker_msg.content
        assert "React to event [1709912345]." in picker_msg.content
        assert "npc_1" in picker_msg.content
        assert "npc_2" in picker_msg.content

    @pytest.mark.asyncio
    async def test_picker_no_separate_inline_description(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Scenario: Picker message does not inline event description separately."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        candidates = [
            {"game_id": "npc_1", "name": "Echo"},
            {"game_id": "npc_2", "name": "Wolf"},
        ]
        event = {"type": "death", "ts": 5000, "context": {"actor": {"name": "A"}, "victim": {"name": "B"}}}
        event_list_text = "[5000] DEATH — A killed B (witnesses: Echo, Wolf)"

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "npc_1"
        mock_llm_client.complete = _capture

        await manager._run_speaker_picker(candidates, event, mock_llm_client, event_list_text=event_list_text)

        picker_msg = captured[0][-1]
        # Should NOT contain old-style "Event: DEATH\nActor: A\nVictim: B"
        assert "Event:" not in picker_msg.content
        assert "Actor:" not in picker_msg.content

    @pytest.mark.asyncio
    async def test_picker_empty_event_list(self, mock_llm_client, mock_state_client, mock_background_generator):
        """Picker with no event list still works (just ts pointer + candidates)."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        candidates = [
            {"game_id": "npc_1", "name": "Echo"},
            {"game_id": "npc_2", "name": "Wolf"},
        ]
        event = {"type": "idle", "ts": 3000, "context": {}}

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "npc_1"
        mock_llm_client.complete = _capture

        await manager._run_speaker_picker(candidates, event, mock_llm_client, event_list_text="")

        picker_msg = captured[0][-1]
        assert "React to event [3000]." in picker_msg.content
        assert "**Recent events in area:**" not in picker_msg.content
```

**Step 2: Run tests to verify they fail**

Run: `talker-tests MCP run_tests { pattern: "TestPickerWithEventList" }`
Expected: FAIL — `_run_speaker_picker()` does not accept `event_list_text` parameter

**Step 3: Update _run_speaker_picker**

In `conversation.py`, modify `_run_speaker_picker` signature and body:

1. Add `event_list_text: str = ""` parameter
2. Replace the picker message construction to use event list + [ts] pointer format:

```python
    async def _run_speaker_picker(
        self,
        candidates: list[dict[str, Any]],
        event: dict[str, Any],
        llm_client: LLMClient,
        dynamic_world_line: str = "",
        event_list_text: str = "",
    ) -> dict[str, Any]:
```

Replace the message construction block:
```python
        event_desc = build_event_description(event)
        candidate_ids_list = [str(c.get("game_id", "")) for c in candidates]
        ids_str = ", ".join(candidate_ids_list)

        parts: list[str] = []
        if dynamic_world_line:
            parts.append(dynamic_world_line)
        parts.append(event_desc)
        parts.append(f"Candidates: {ids_str}")
        parts.append(
            "Pick the character who would most naturally react to this event. "
            "Respond with ONLY their character ID."
        )
```

With:
```python
        ts = event.get("ts", 0)
        candidate_ids_list = [str(c.get("game_id", "")) for c in candidates]
        ids_str = ", ".join(candidate_ids_list)

        parts: list[str] = []
        if dynamic_world_line:
            parts.append(dynamic_world_line)
        if event_list_text:
            parts.append(f"\n**Recent events in area:**\n{event_list_text}")
        parts.append(f"\nReact to event [{ts}].")
        parts.append(f"Candidates: {ids_str}")
        parts.append(
            "Pick the character who would most naturally react. "
            "Respond with ONLY their character ID."
        )
```

Also update the `handle_event()` caller to pass `event_list_text`:
```python
        speaker = await self._run_speaker_picker(
            candidates, event, llm_client,
            dynamic_world_line=dynamic_world_line,
            event_list_text=event_list_text,
        )
```

**Step 4: Run tests to verify they pass**

Run: `talker-tests MCP run_tests { pattern: "TestPickerWithEventList" }`
Expected: PASS

Also run existing picker tests to check for regressions:
Run: `talker-tests MCP run_tests { pattern: "TestPickerPointerFormat|TestPickerEphemeralCleanup|TestSpeakerPicker" }`
Expected: Some may need updating to account for the new format. Fix any that assert old `Event:` format.

**Step 5: Commit**

```bash
git add talker_service/src/talker_service/dialogue/conversation.py talker_service/tests/test_conversation.py
git commit -m "feat: picker uses event list with [ts] pointers"
```

---

### Task 6: Dialogue with ephemeral user message + event list

**Files:**
- Modify: `talker_service/src/talker_service/dialogue/conversation.py` — `_run_dialogue_generation()`
- Modify: `talker_service/tests/test_conversation.py`

The dialogue step changes:
1. User message includes speaker-filtered event list with `[ts]` pointers (no inline description)
2. User message is now **ephemeral** — removed after LLM call, only assistant response persists

**Step 1: Write the failing tests**

Append to `talker_service/tests/test_conversation.py`:

```python
class TestDialogueWithEventList:
    """Tests for dialogue step with ephemeral user message + event list."""

    @pytest.mark.asyncio
    async def test_dialogue_includes_speaker_filtered_events(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: Dialogue prompt includes speaker-filtered event list."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None}
        event = {"type": "death", "ts": 1709912345, "context": {}}
        speaker_event_text = "[1709912001] CALLOUT — Echo (witnesses: Echo)\n[1709912345] DEATH — Duty killed Freedom (witnesses: Echo, Wolf)"

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "For the Zone!"
        mock_llm_client.complete = _capture

        await manager._run_dialogue_generation(
            speaker, event, mock_llm_client,
            speaker_event_list_text=speaker_event_text,
        )

        user_msg = captured[0][-1]
        assert "**Recent events witnessed by Echo:**" in user_msg.content
        assert "[1709912345]" in user_msg.content
        assert "React to event [1709912345] as **Echo** (ID: npc_1)." in user_msg.content

    @pytest.mark.asyncio
    async def test_dialogue_no_separate_event_description(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Dialogue should not inline event description separately from event list."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None}
        event = {"type": "death", "ts": 5000, "context": {"actor": {"name": "A"}, "victim": {"name": "B"}}}

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "Words."
        mock_llm_client.complete = _capture

        await manager._run_dialogue_generation(
            speaker, event, mock_llm_client,
            speaker_event_list_text="[5000] DEATH — A killed B (witnesses: Echo)",
        )

        user_msg = captured[0][-1]
        assert "Event:" not in user_msg.content
        assert "Actor:" not in user_msg.content

    @pytest.mark.asyncio
    async def test_dialogue_user_message_is_ephemeral(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: After dialogue, user message is removed; only assistant response persists."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None}
        mock_llm_client.complete = AsyncMock(return_value="Dialogue text.")

        pre_count = len(manager._messages)

        await manager._run_dialogue_generation(
            speaker, {"type": "idle", "ts": 100, "context": {}}, mock_llm_client,
            speaker_event_list_text="",
        )

        # Only assistant response should be added (net +1)
        assert len(manager._messages) == pre_count + 1
        assert manager._messages[-1].role == "assistant"
        assert manager._messages[-1].content == "Dialogue text."
        # No user message in the final state
        for msg in manager._messages[pre_count:]:
            assert msg.role != "user"

    @pytest.mark.asyncio
    async def test_dialogue_no_narrative(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: Speaker has no personal narrative memories yet."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "npc_1", "name": "Nobody", "faction": "loner", "background": None}

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "..."
        mock_llm_client.complete = _capture

        await manager._run_dialogue_generation(
            speaker, {"type": "idle", "ts": 99, "context": {}}, mock_llm_client,
            speaker_event_list_text="",
        )

        user_msg = captured[0][-1]
        assert "Personal memories:" not in user_msg.content
        assert "React to event [99]" in user_msg.content

    @pytest.mark.asyncio
    async def test_events_not_in_context_block(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Scenario: Events appear in user message at Layer 4, not in context block."""
        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        mock_state_client.execute_batch.return_value = BatchResult({
            "mem_summaries": {"ok": True, "data": []},
            "mem_digests": {"ok": True, "data": []},
            "mem_cores": {"ok": True, "data": []},
        })

        speaker = {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None}

        captured = []
        async def _capture(messages, **kw):
            captured.append(list(messages))
            return "OK"
        mock_llm_client.complete = _capture

        await manager._run_dialogue_generation(
            speaker, {"type": "death", "ts": 5000, "context": {}}, mock_llm_client,
            speaker_event_list_text="[5000] DEATH — events here (witnesses: Echo)",
        )

        # Context block (_messages[1]) should NOT contain event lines
        context_block = manager._messages[1].content
        assert "[5000]" not in context_block
        assert "witnesses:" not in context_block
```

**Step 2: Run tests to verify they fail**

Run: `talker-tests MCP run_tests { pattern: "TestDialogueWithEventList" }`
Expected: FAIL — `_run_dialogue_generation()` does not accept `speaker_event_list_text` parameter, and user message is currently persistent

**Step 3: Update _run_dialogue_generation**

Modify `_run_dialogue_generation` in `conversation.py`:

1. Add `speaker_event_list_text: str = ""` parameter (replaces `witness_events`)
2. Build user message with `[ts]` pointer format
3. Make user message ephemeral (pop after LLM call, keep only assistant response)

Replace the method signature:
```python
    async def _run_dialogue_generation(
        self,
        speaker: dict[str, Any],
        event: dict[str, Any],
        llm_client: LLMClient,
        dynamic_world_line: str = "",
        speaker_event_list_text: str = "",
    ) -> str:
```

Replace the message construction and LLM call:
```python
        narrative = await self._inject_speaker_memory(speaker)
        speaker_name = speaker.get("name", "Unknown")
        speaker_id = str(speaker.get("game_id", ""))
        ts = event.get("ts", 0)

        parts: list[str] = []
        if dynamic_world_line:
            parts.append(dynamic_world_line)
        if speaker_event_list_text:
            parts.append(f"\n**Recent events witnessed by {speaker_name}:**\n{speaker_event_list_text}")
        parts.append(f"\nReact to event [{ts}] as **{speaker_name}** (ID: {speaker_id}).")
        if narrative:
            parts.append(f"\n**Personal memories:**\n{narrative}")
        parts.append(f"\nGenerate {speaker_name}'s dialogue — just the spoken words, nothing else.")
        user_content = "\n".join(parts)

        self._messages.append(Message(role="user", content=user_content))

        llm_opts = LLMOptions(reasoning=self.reasoning) if self.reasoning else None

        try:
            response = await llm_client.complete(self._messages, opts=llm_opts)
        except Exception as e:
            logger.error("Dialogue generation LLM call failed: {}", e)
            self._messages.pop()
            return ""

        dialogue_text = response.strip()

        # Ephemeral: remove user message, keep only assistant response
        self._messages.pop()  # remove user message
        self._messages.append(Message(role="assistant", content=dialogue_text))

        return dialogue_text
```

Also update the `handle_event()` caller to compute speaker-filtered event list and pass it:
```python
        # Filter events to those witnessed by the speaker
        speaker_name = speaker.get("name", "Unknown")
        filtered_events, filtered_witness = filter_events_by_name(
            unique_events, witness_map, speaker_name,
        )
        speaker_event_text = build_event_list_text(filtered_events, filtered_witness)

        # Step 2: Dialogue generation
        dialogue_text = await self._run_dialogue_generation(
            speaker, event, llm_client,
            dynamic_world_line=dynamic_world_line,
            speaker_event_list_text=speaker_event_text,
        )
```

**Step 4: Run tests to verify they pass**

Run: `talker-tests MCP run_tests { pattern: "TestDialogueWithEventList" }`
Expected: PASS

Also check existing dialogue tests for regressions:
Run: `talker-tests MCP run_tests { pattern: "TestDialogueMessageFormat|TestDialogueGeneration" }`
Expected: Some will need updating (old tests check for `_messages[-2]` being user message, now it's ephemeral)

**Step 5: Commit**

```bash
git add talker_service/src/talker_service/dialogue/conversation.py talker_service/tests/test_conversation.py
git commit -m "feat: dialogue uses ephemeral user message with [ts] pointers"
```

---

### Task 7: Update prompt builders + full flow integration test

**Files:**
- Modify: `talker_service/src/talker_service/prompts/dialogue.py`
- Modify: `talker_service/tests/test_conversation.py`

The prompt builder functions in `dialogue.py` need to be updated to match the new format, or marked as deprecated if `_run_dialogue_generation` now builds messages inline. The `build_dialogue_user_message()` function is currently unused after Task 6 inlines the construction — either update it to match the new format or remove it.

**Step 1: Update build_dialogue_user_message to new format**

```python
def build_dialogue_user_message(
    speaker_name: str,
    speaker_id: str,
    ts: int,
    narrative: str,
    *,
    dynamic_world_line: str = "",
    speaker_event_list_text: str = "",
) -> str:
    """Build the user message for the dialogue generation step.

    Uses [ts] pointer format with speaker-filtered event list.
    """
    parts: list[str] = []
    if dynamic_world_line:
        parts.append(dynamic_world_line)
    if speaker_event_list_text:
        parts.append(
            f"\n**Recent events witnessed by {speaker_name}:**\n{speaker_event_list_text}"
        )
    parts.append(f"\nReact to event [{ts}] as **{speaker_name}** (ID: {speaker_id}).")
    if narrative:
        parts.append(f"\n**Personal memories:**\n{narrative}")
    parts.append(
        f"\nGenerate {speaker_name}'s dialogue — just the spoken words, nothing else."
    )
    return "\n".join(parts)
```

**Step 2: Write integration test for full flow**

```python
class TestFullEventFlow:
    """Integration test: full handle_event with event list + [ts] pointers."""

    @pytest.mark.asyncio
    async def test_full_flow_events_fetched_deduped_filtered(
        self, mock_llm_client, mock_state_client, mock_background_generator,
    ):
        """Full flow: events fetched → deduped → picker sees union → dialogue sees speaker-filtered."""
        candidates = [
            {"game_id": "npc_1", "name": "Echo", "faction": "loner", "background": None},
            {"game_id": "npc_2", "name": "Wolf", "faction": "loner", "background": None},
        ]
        event = {"type": "death", "ts": 5000, "context": {"actor": {"name": "A"}, "victim": {"name": "B"}}}

        call_count = 0
        captured_picker = []
        captured_dialogue = []

        async def _complete(messages, opts=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                captured_picker.append(list(messages))
                return "npc_1"  # picker picks Echo
            captured_dialogue.append(list(messages))
            return "Blyat!"

        mock_llm_client.complete = AsyncMock(side_effect=_complete)

        async def _batch(batch, **kw):
            result_data = {}
            for q in batch.query_ids:
                if q == "events_npc_1":
                    result_data[q] = {"ok": True, "data": [
                        {"ts": 4000, "type": "callout", "context": {"actor": {"name": "Echo"}}},
                        {"ts": 5000, "type": "death", "context": {"actor": {"name": "A"}, "victim": {"name": "B"}}},
                    ]}
                elif q == "events_npc_2":
                    result_data[q] = {"ok": True, "data": [
                        {"ts": 5000, "type": "death", "context": {"actor": {"name": "A"}, "victim": {"name": "B"}}},
                    ]}
                elif q == "scene":
                    result_data[q] = {"ok": True, "data": {"loc": "l01_escape", "weather": "clear", "time": {"h": 14, "m": 35}, "emission": False, "psy_storm": False, "sheltering": False, "campfire": None, "brain_scorcher_disabled": False, "miracle_machine_disabled": False}}
                elif q == "alive":
                    result_data[q] = {"ok": True, "data": {}}
                else:
                    result_data[q] = {"ok": True, "data": []}
            return BatchResult(result_data)

        mock_state_client.execute_batch = AsyncMock(side_effect=_batch)

        manager = ConversationManager(
            llm_client=mock_llm_client,
            state_client=mock_state_client,
            background_generator=mock_background_generator,
        )

        speaker_id, dialogue = await manager.handle_event(event, candidates, "", {})

        assert speaker_id == "npc_1"
        assert dialogue == "Blyat!"

        # Picker should see union event list (both ts 4000 and 5000)
        picker_msg = captured_picker[0][-1]
        assert "[4000]" in picker_msg.content
        assert "[5000]" in picker_msg.content
        assert "React to event [5000]." in picker_msg.content

        # Dialogue should see only Echo's events (ts 4000 and 5000, since Echo saw both)
        dialogue_msg = captured_dialogue[0][-1]
        assert "[4000]" in dialogue_msg.content
        assert "[5000]" in dialogue_msg.content
        assert "React to event [5000] as **Echo**" in dialogue_msg.content

        # User message should be ephemeral — only assistant response persists
        assert manager._messages[-1].role == "assistant"
        assert manager._messages[-1].content == "Blyat!"
```

**Step 3: Run all tests**

Run: `talker-tests MCP run_tests { pattern: "test_conversation" }`
Expected: PASS (may need to fix existing tests that assert old format)

**Step 4: Commit**

```bash
git add talker_service/src/talker_service/prompts/dialogue.py talker_service/tests/test_conversation.py
git commit -m "feat: update prompt builders and add full-flow integration test"
```

---

### Task 8: Clean up stale code + final verification

**Files:**
- Modify: `talker_service/src/talker_service/dialogue/conversation.py` — remove unused imports/functions
- Modify: `talker_service/tests/test_conversation.py` — fix any remaining broken tests

**Step 1: Remove stale `witness_events` parameter and old `build_event_description` usage**

In `conversation.py`:
- Remove the `build_event_description` import from `prompts.picker` (if no longer used in `_run_speaker_picker`)
- Remove the old `witness_events: list[dict] | None` parameter from `_run_dialogue_generation` (replaced by `speaker_event_list_text`)
- Keep `build_witness_text()` as it's still used by `_inject_witness_events()` for post-dialogue memory storage

In `prompts/picker.py`:
- Keep `build_event_description()` if anything else imports it; otherwise remove
- Keep `parse_picker_response()` (still needed)

**Step 2: Fix broken existing tests**

Tests that may need updating:
- `TestPickerPointerFormat`: Now expects [ts] format instead of `Event: DEATH`
- `TestDialogueMessageFormat`: Now dialogue user message is ephemeral (no `_messages[-2]` user msg)
- `TestPickerEphemeralCleanup`: May need adjustment for new param
- `TestHandleEvent`: Flow changed — events fetched before picker now

Update assertions to match new behavior:
- Where tests check `_messages[-2]` for user message → check that user message is NOT in final `_messages`
- Where tests check `"Event:"` in picker content → check `"React to event ["` format
- Where tests mock `execute_batch` → account for the new events batch call

**Step 3: Run full test suite**

Run: `talker-tests MCP run_tests {}`
Expected: ALL PASS

Run: `lua-tests MCP run_tests { path: "tests/infra/ws/" }`
Expected: ALL PASS (Lua serializer unchanged)

**Step 4: Commit**

```bash
git add -u
git commit -m "refactor: clean up stale code and fix existing tests"
```
