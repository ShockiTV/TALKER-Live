"""Tests for event list formatting helpers.

Covers specs:
- specs/event-list-assembly/spec.md
- specs/witness-event-injection/spec.md (filter_events_for_speaker)
"""

import pytest

from talker_service.dialogue.event_list import (
    assemble_event_list,
    build_event_list_text,
    filter_events_for_speaker,
    format_event_line,
)


# ---------------------------------------------------------------------------
# TestAssembleEventList
# ---------------------------------------------------------------------------


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

    def test_empty_candidates(self):
        """No candidates produces empty results."""
        unique_events, witness_map = assemble_event_list({}, {})

        assert unique_events == {}
        assert witness_map == {}

    def test_unknown_candidate_id_falls_back_to_id_as_name(self):
        """Candidate ID not in names map uses ID as fallback name."""
        events_by_candidate = {
            "npc_99": [{"ts": 100, "type": "idle", "context": {}}],
        }
        candidate_names = {}  # empty names map

        unique_events, witness_map = assemble_event_list(events_by_candidate, candidate_names)

        assert 100 in unique_events
        assert "npc_99" in witness_map[100]


# ---------------------------------------------------------------------------
# TestFilterEventsForSpeaker
# ---------------------------------------------------------------------------


class TestFilterEventsForSpeaker:
    """Tests for filter_events_for_speaker() (name-based)."""

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
        # All witnesses preserved, not just the speaker
        assert filtered_witness[100] == {"Echo", "Wolf"}
        assert filtered_witness[300] == {"Echo", "Fanatic"}

    def test_speaker_witnessed_no_events(self):
        """Speaker not in any witness set returns empty."""
        unique_events = {100: {"type": "death", "context": {}}}
        witness_map = {100: {"Wolf"}}

        filtered_events, filtered_witness = filter_events_for_speaker(
            unique_events, witness_map, "Echo",
        )

        assert len(filtered_events) == 0

    def test_empty_events(self):
        """Empty inputs return empty outputs."""
        filtered_events, filtered_witness = filter_events_for_speaker({}, {}, "Echo")

        assert len(filtered_events) == 0
        assert len(filtered_witness) == 0

    def test_all_events_witnessed_by_speaker(self):
        """Speaker in all events returns all events."""
        unique_events = {
            1: {"type": "death", "context": {}},
            2: {"type": "idle", "context": {}},
        }
        witness_map = {
            1: {"Echo", "Wolf"},
            2: {"Echo"},
        }

        filtered_events, _ = filter_events_for_speaker(unique_events, witness_map, "Echo")

        assert len(filtered_events) == 2


class TestFormatEventLine:
    def test_death_event_two_witnesses(self):
        event = {
            "type": "death",
            "context": {
                "actor": {"name": "Freedom Soldier", "game_id": "1"},
                "victim": {"name": "Monolith Fighter", "game_id": "2"},
            },
        }
        result = format_event_line(1709912001, event, {"Echo", "Wolf"})
        assert result == "[1709912001] DEATH — Freedom Soldier killed Monolith Fighter (witnesses: Echo, Wolf)"

    def test_event_one_witness(self):
        event = {
            "type": "callout",
            "context": {
                "actor": {"name": "Duty Soldier", "game_id": "3"},
                "target": {"name": "Stalker Newbie", "game_id": "4"},
            },
        }
        result = format_event_line(1709912078, event, {"Echo"})
        assert "[1709912078] CALLOUT" in result
        assert "(witnesses: Echo)" in result

    def test_event_no_victim(self):
        event = {
            "type": "emission",
            "context": {"actor": {"name": "Zone", "game_id": "0"}},
        }
        result = format_event_line(100, event, {"Wolf"})
        assert "[100] EMISSION" in result
        assert "Zone" in result

    def test_witness_names_sorted_for_determinism(self):
        event = {
            "type": "death",
            "context": {
                "actor": {"name": "A", "game_id": "1"},
                "victim": {"name": "B", "game_id": "2"},
            },
        }
        r1 = format_event_line(1, event, {"Zulu", "Alpha", "Mike"})
        r2 = format_event_line(1, event, {"Mike", "Alpha", "Zulu"})
        assert r1 == r2
        assert "(witnesses: Alpha, Mike, Zulu)" in r1


class TestBuildEventListText:
    def test_events_sorted_by_ts_ascending(self):
        events = {
            1709912345: {
                "type": "death",
                "context": {"actor": {"name": "A", "game_id": "1"}, "victim": {"name": "B", "game_id": "2"}},
            },
            1709912001: {
                "type": "callout",
                "context": {"actor": {"name": "C", "game_id": "3"}},
            },
            1709912078: {
                "type": "injury",
                "context": {"actor": {"name": "D", "game_id": "4"}, "victim": {"name": "E", "game_id": "5"}},
            },
        }
        witness_map = {
            1709912345: {"Echo", "Wolf"},
            1709912001: {"Echo"},
            1709912078: {"Wolf"},
        }
        result = build_event_list_text(events, witness_map)
        lines = result.strip().split("\n")
        assert len(lines) == 3
        assert lines[0].startswith("[1709912001]")
        assert lines[1].startswith("[1709912078]")
        assert lines[2].startswith("[1709912345]")

    def test_empty_events(self):
        result = build_event_list_text({}, {})
        assert result == ""
