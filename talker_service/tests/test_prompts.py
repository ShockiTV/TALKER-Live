"""Tests for prompts module.

Tests for deleted prompt builder functions (create_pick_speaker_prompt,
create_dialogue_request_prompt, create_compress_memories_prompt,
create_update_narrative_prompt, create_transcription_prompt) were removed
during tools-based-memory migration — those functions are replaced by
tool-based conversation in ConversationManager.
"""

import pytest

from talker_service.prompts import (
    Character,
    Event,
    MemoryContext,
    NarrativeCue,
    get_faction_description,
    get_faction_relation,
    get_faction_relations_text,
)
from talker_service.prompts.helpers import (
    describe_character,
    describe_character_with_id,
    describe_event,
    is_junk_event,
    was_witnessed_by,
    inject_time_gaps,
)
from talker_service.llm.models import Message


# ============================================================================
# Model Tests
# ============================================================================

class TestCharacter:
    """Tests for Character model."""
    
    def test_create_character(self):
        char = Character(
            game_id="123",
            name="Hip",
            faction="stalker",
            experience="Veteran",
            reputation=500,
        )
        assert char.game_id == "123"
        assert char.name == "Hip"
        assert char.faction == "stalker"
        assert char.experience == "Veteran"
        assert char.reputation == 500
    
    def test_character_from_dict(self):
        data = {
            "game_id": 456,
            "name": "Wolf",
            "faction": "stalker",
            "experience": "Expert",
            "reputation": 1000,
        }
        char = Character.from_dict(data)
        assert char.game_id == "456"
        assert char.name == "Wolf"
    
    def test_character_from_dict_with_missing_fields(self):
        data = {"game_id": "1", "name": "Unknown"}
        char = Character.from_dict(data)
        assert char.game_id == "1"
        assert char.name == "Unknown"
        assert char.faction == "stalker"  # default
        assert char.experience == "Experienced"  # default


class TestEvent:
    """Tests for Event model."""
    
    def test_create_event(self):
        event = Event(
            type="DEATH",
            context={"victim": {"name": "Bandit"}},
            game_time_ms=1000,
        )
        assert event.type == "DEATH"
        assert event.context == {"victim": {"name": "Bandit"}}
        assert event.game_time_ms == 1000
    
    def test_event_from_dict(self):
        data = {
            "type": "DIALOGUE",
            "context": {"speaker": {"name": "Hip"}, "text": "Hello!"},
            "game_time_ms": 2000,
            "world_context": "In Cordon",  # Should be ignored (backward compat)
            "flags": {"is_idle": True},
        }
        event = Event.from_dict(data)
        assert event.type == "DIALOGUE"
        # world_context intentionally not stored - queried JIT during prompt building
        assert event.flags == {"is_idle": True}
    
    def test_event_from_dict_with_legacy_content(self):
        """Legacy content field is ignored - events must be typed."""
        data = {"content": "Something happened", "game_time_ms": 500}
        event = Event.from_dict(data)
        # content field no longer exists
        assert event.type is None


# ============================================================================
# Helper Tests
# ============================================================================

class TestDescribeCharacter:
    """Tests for describe_character helper."""
    
    def test_describe_human_character(self):
        char = Character(
            game_id="123",
            name="Hip",
            faction="stalker",
            experience="Veteran",
            reputation=500,
        )
        desc = describe_character(char)
        assert "Hip" in desc
        assert "Veteran" in desc
        assert "Loner" in desc  # stalker resolves to Loner
        assert "Reputation: 500" in desc
    
    def test_describe_monster(self):
        char = Character(
            game_id="999",
            name="Bloodsucker",
            faction="monster",
            experience="",
            reputation=0,
        )
        desc = describe_character(char)
        assert "Bloodsucker" in desc
        assert "Monster" in desc  # monster resolves to Monster
    
    def test_describe_character_with_id(self):
        char = Character(
            game_id="456",
            name="Wolf",
            faction="stalker",
            experience="Expert",
            reputation=1000,
        )
        desc = describe_character_with_id(char)
        assert "[ID: 456]" in desc
        assert "Wolf" in desc


class TestDescribeEvent:
    """Tests for describe_event helper."""
    
    def test_describe_death_event(self):
        victim = Character(game_id="1", name="Bandit", faction="bandit", experience="Novice", reputation=-500)
        killer = Character(game_id="2", name="Hip", faction="stalker", experience="Veteran", reputation=500)
        event = Event(
            type="DEATH",
            context={"victim": victim.__dict__, "killer": killer.__dict__},
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "killed" in desc.lower() or "death" in desc.lower() or "bandit" in desc.lower()
    
    def test_describe_dialogue_event(self):
        speaker = Character(game_id="1", name="Hip", faction="stalker", experience="Veteran", reputation=500)
        event = Event(
            type="DIALOGUE",
            context={"speaker": speaker.__dict__, "text": "Stay safe out there"},
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "Hip" in desc or "said" in desc.lower()

    def test_describe_event_case_insensitive(self):
        """Event types from Lua are lowercase - Python must handle both."""
        speaker = Character(game_id="1", name="Wolf", faction="stalker", experience="Veteran", reputation=500)
        # Lua sends lowercase event types
        event = Event(
            type="dialogue",  # lowercase like Lua EventType.DIALOGUE = "dialogue"
            context={"speaker": speaker.__dict__, "text": "Watch your back"},
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "Wolf" in desc
        assert "Watch your back" in desc
    
    def test_describe_unknown_event(self):
        """Unknown event types return formatted fallback."""
        event = Event(
            type="CUSTOM_TYPE",
            context={},
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "Event: CUSTOM_TYPE" in desc

    def test_describe_compressed_event_with_narrative(self):
        """COMPRESSED events use context.narrative for the summary."""
        event = Event(
            type="COMPRESSED",
            context={"narrative": "Encountered dangerous anomalies and found an artifact."},
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "[COMPRESSED MEMORY]" in desc
        assert "Encountered dangerous anomalies" in desc

    def test_describe_compressed_event_without_narrative(self):
        """COMPRESSED events without narrative show fallback."""
        event = Event(
            type="COMPRESSED",
            context={},
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "[COMPRESSED MEMORY]" in desc
        assert "no narrative available" in desc

    def test_describe_task_event_with_giver(self):
        """Task event with task_giver shows giver name and resolved faction display name."""
        actor = Character(game_id="1", name="Player", faction="stalker", experience="Veteran", reputation=500)
        task_giver = Character(game_id="2", name="General Voronin", faction="dolg", experience="Master", reputation=2000)
        event = Event(
            type="TASK",
            context={
                "actor": actor.__dict__,
                "task_status": "completed",
                "task_name": "Patrol the Garbage",
                "task_giver": task_giver.__dict__,
            },
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "Patrol the Garbage" in desc
        assert "General Voronin" in desc
        assert "Duty" in desc  # technical "dolg" resolved to display "Duty"

    def test_describe_task_event_without_giver(self):
        """Task event without task_giver omits giver part gracefully."""
        actor = Character(game_id="1", name="Player", faction="stalker", experience="Veteran", reputation=500)
        event = Event(
            type="TASK",
            context={
                "actor": actor.__dict__,
                "task_status": "completed",
                "task_name": "Find the artifact",
            },
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "Find the artifact" in desc
        assert "completed" in desc
        assert " for " not in desc  # No giver part appended


class TestDescribeMapTransitionEvent:
    """Tests for MAP_TRANSITION event formatting with technical IDs."""
    
    def test_map_transition_solo_travel(self):
        """Test MAP_TRANSITION with actor traveling alone."""
        actor = Character(game_id="1", name="Wolf", faction="stalker", experience="Veteran", reputation=1000)
        event = Event(
            type="MAP_TRANSITION",
            context={
                "actor": actor.__dict__,
                "source": "l01_escape",
                "destination": "l02_garbage",
                "visit_count": 1,
                "companions": [],
            },
            game_time_ms=1000,
        )
        desc = describe_event(event)
        # Should resolve technical IDs to human names
        assert "Wolf" in desc
        assert "Cordon" in desc
        assert "Garbage" in desc
        assert "for the first time" in desc
        # Should include destination description
        assert "radioactive trash" in desc.lower() or "connecting" in desc.lower()
    
    def test_map_transition_with_companions(self):
        """Test MAP_TRANSITION with companions."""
        actor = Character(game_id="1", name="Wolf", faction="stalker", experience="Veteran", reputation=1000)
        event = Event(
            type="MAP_TRANSITION",
            context={
                "actor": actor.__dict__,
                "source": "l01_escape",
                "destination": "l05_bar",
                "visit_count": 2,
                "companions": [
                    {"name": "Hip", "game_id": "2", "faction": "stalker"},
                    {"name": "Fanatic", "game_id": "3", "faction": "stalker"},
                ],
            },
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "Wolf" in desc
        assert "travelling companions" in desc
        assert "Hip" in desc
        assert "Fanatic" in desc
        assert "Cordon" in desc
        assert "Rostok" in desc
        assert "for the 2nd time" in desc
    
    def test_map_transition_visit_count_formatting(self):
        """Test visit count formatting variations."""
        actor = Character(game_id="1", name="Wolf", faction="stalker", experience="Veteran", reputation=1000)
        
        # First visit
        event1 = Event(
            type="MAP_TRANSITION",
            context={"actor": actor.__dict__, "source": "jupiter", "destination": "zaton", "visit_count": 1, "companions": []},
            game_time_ms=1000,
        )
        assert "for the first time" in describe_event(event1)
        
        # Second visit
        event2 = Event(
            type="MAP_TRANSITION",
            context={"actor": actor.__dict__, "source": "jupiter", "destination": "zaton", "visit_count": 2, "companions": []},
            game_time_ms=1000,
        )
        assert "for the 2nd time" in describe_event(event2)
        
        # Third visit
        event3 = Event(
            type="MAP_TRANSITION",
            context={"actor": actor.__dict__, "source": "jupiter", "destination": "zaton", "visit_count": 3, "companions": []},
            game_time_ms=1000,
        )
        assert "for the 3rd time" in describe_event(event3)
        
        # Fourth+ visits
        event4 = Event(
            type="MAP_TRANSITION",
            context={"actor": actor.__dict__, "source": "jupiter", "destination": "zaton", "visit_count": 4, "companions": []},
            game_time_ms=1000,
        )
        assert "again" in describe_event(event4)
    
    def test_map_transition_unknown_location(self):
        """Test MAP_TRANSITION with unknown location falls back to ID."""
        actor = Character(game_id="1", name="Wolf", faction="stalker", experience="Veteran", reputation=1000)
        event = Event(
            type="MAP_TRANSITION",
            context={
                "actor": actor.__dict__,
                "source": "unknown_zone",
                "destination": "another_unknown",
                "visit_count": 1,
                "companions": [],
            },
            game_time_ms=1000,
        )
        desc = describe_event(event)
        # Unknown locations should use the technical ID as-is
        assert "unknown_zone" in desc
        assert "another_unknown" in desc


class TestIsJunkEvent:
    """Tests for is_junk_event helper."""
    
    def test_artifact_is_junk(self):
        event = Event(type="ARTIFACT", context={}, game_time_ms=1000)
        assert is_junk_event(event) is True
    
    def test_anomaly_is_junk(self):
        event = Event(type="ANOMALY", context={}, game_time_ms=1000)
        assert is_junk_event(event) is True
    
    def test_reload_is_junk(self):
        event = Event(type="RELOAD", context={}, game_time_ms=1000)
        assert is_junk_event(event) is True
    
    def test_weapon_jam_is_junk(self):
        event = Event(type="WEAPON_JAM", context={}, game_time_ms=1000)
        assert is_junk_event(event) is True
    
    def test_death_is_not_junk(self):
        event = Event(type="DEATH", context={}, game_time_ms=1000)
        assert is_junk_event(event) is False
    
    def test_dialogue_is_not_junk(self):
        event = Event(type="DIALOGUE", context={}, game_time_ms=1000)
        assert is_junk_event(event) is False


class TestWasWitnessedBy:
    """Tests for was_witnessed_by helper."""
    
    def test_character_in_witnesses(self):
        witness = Character(game_id="123", name="Hip", faction="stalker", experience="Veteran", reputation=500)
        event = Event(
            type="DEATH",
            context={},
            game_time_ms=1000,
            witnesses=[witness],
        )
        assert was_witnessed_by(event, "123") is True
        assert was_witnessed_by(event, "999") is False
    
    def test_no_witnesses(self):
        event = Event(type="DEATH", context={}, game_time_ms=1000, witnesses=None)
        assert was_witnessed_by(event, "123") is False


# ============================================================================
# Faction Tests
# ============================================================================

class TestFactions:
    """Tests for faction helpers."""
    
    def test_get_faction_description(self):
        desc = get_faction_description("dolg")  # technical ID for Duty
        assert "paramilitary" in desc.lower() or "zone" in desc.lower()
    
    def test_get_faction_description_unknown(self):
        desc = get_faction_description("UnknownFaction")
        assert desc == ""
    
    def test_get_faction_relation_hostile(self):
        assert get_faction_relation("dolg", "freedom") == -1
        assert get_faction_relation("freedom", "dolg") == -1
    
    def test_get_faction_relation_allied(self):
        assert get_faction_relation("dolg", "ecolog") == 1
    
    def test_get_faction_relation_same(self):
        assert get_faction_relation("Duty", "Duty") == 1
    
    def test_get_faction_relation_neutral(self):
        # Unknown factions default to neutral
        assert get_faction_relation("Duty", "UnknownFaction") == 0
    
    def test_get_faction_relations_text(self):
        text = get_faction_relations_text("dolg", {"freedom", "bandit"})
        assert "HOSTILE" in text
        assert "Duty" in text  # dolg resolves to Duty in display


class TestMessage:
    """Tests for Message class."""
    
    def test_system_message(self):
        msg = Message.system("System instruction")
        assert msg.role == "system"
        assert msg.content == "System instruction"
    
    def test_user_message(self):
        msg = Message.user("User input")
        assert msg.role == "user"
        assert msg.content == "User input"
    
    def test_to_dict(self):
        msg = Message(role="assistant", content="Response")
        d = msg.to_dict()
        assert d == {"role": "assistant", "content": "Response"}


# ============================================================================
# Time Gap Injection Tests
# ============================================================================

class TestInjectTimeGaps:
    """Tests for inject_time_gaps function."""
    
    def test_no_events_returns_empty(self):
        """Empty events list returns empty list."""
        result = inject_time_gaps([], last_update_time_ms=0)
        assert result == []
    
    def test_single_event_no_gap(self):
        """Single event with no prior timestamp returns unchanged."""
        event = Event(type="DEATH", game_time_ms=1000)
        result = inject_time_gaps([event], last_update_time_ms=0)
        assert len(result) == 1
        assert result[0].type == "DEATH"
    
    def test_single_event_with_large_gap_from_last_update(self):
        """Single event with large gap from last_update_time injects NarrativeCue."""
        MS_PER_HOUR = 60 * 60 * 1000
        last_update = 1000
        event = Event(type="DEATH", game_time_ms=last_update + (13 * MS_PER_HOUR))  # 13 hours later
        
        result = inject_time_gaps([event], last_update_time_ms=last_update)
        
        assert len(result) == 2
        assert isinstance(result[0], NarrativeCue)
        assert result[0].type == "TIME_GAP"
        assert "13 hours" in result[0].message
        assert result[1].type == "DEATH"
    
    def test_two_events_no_gap(self):
        """Two events close in time have no GAP injected."""
        MS_PER_HOUR = 60 * 60 * 1000
        events = [
            Event(type="DEATH", game_time_ms=1000),
            Event(type="DIALOGUE", game_time_ms=1000 + (1 * MS_PER_HOUR)),  # 1 hour later
        ]
        
        result = inject_time_gaps(events, last_update_time_ms=0)
        
        assert len(result) == 2
        assert result[0].type == "DEATH"
        assert result[1].type == "DIALOGUE"
    
    def test_two_events_with_large_gap(self):
        """Two events with large time gap have NarrativeCue injected between them."""
        MS_PER_HOUR = 60 * 60 * 1000
        events = [
            Event(type="DEATH", game_time_ms=1000),
            Event(type="DIALOGUE", game_time_ms=1000 + (24 * MS_PER_HOUR)),  # 24 hours later
        ]
        
        result = inject_time_gaps(events, last_update_time_ms=0)
        
        assert len(result) == 3
        assert result[0].type == "DEATH"
        assert isinstance(result[1], NarrativeCue)
        assert result[1].type == "TIME_GAP"
        assert "24 hours" in result[1].message
        assert result[2].type == "DIALOGUE"
    
    def test_custom_time_gap_threshold(self):
        """Custom time_gap_hours threshold is respected."""
        MS_PER_HOUR = 60 * 60 * 1000
        events = [
            Event(type="DEATH", game_time_ms=1000),
            Event(type="DIALOGUE", game_time_ms=1000 + (8 * MS_PER_HOUR)),  # 8 hours later
        ]
        
        # With default 12 hour threshold, no gap should be injected
        result_default = inject_time_gaps(events, last_update_time_ms=0, time_gap_hours=12)
        assert len(result_default) == 2
        
        # With 6 hour threshold, gap should be injected
        result_custom = inject_time_gaps(events, last_update_time_ms=0, time_gap_hours=6)
        assert len(result_custom) == 3
        assert isinstance(result_custom[1], NarrativeCue)
        assert result_custom[1].type == "TIME_GAP"
    
    def test_narrative_cue_has_correct_properties(self):
        """NarrativeCue has expected properties."""
        MS_PER_HOUR = 60 * 60 * 1000
        events = [
            Event(type="DEATH", game_time_ms=1000),
            Event(type="DIALOGUE", game_time_ms=1000 + (15 * MS_PER_HOUR)),
        ]
        
        result = inject_time_gaps(events, last_update_time_ms=0)
        cue = result[1]
        
        assert isinstance(cue, NarrativeCue)
        assert cue.type == "TIME_GAP"
        assert cue.is_cue is True
        # Cue is placed just after the preceding event (at +1ms)
        assert cue.game_time_ms == 1001
    
    def test_events_sorted_by_time(self):
        """Events are sorted by game_time_ms before gap injection."""
        MS_PER_HOUR = 60 * 60 * 1000
        # Provide events out of order
        events = [
            Event(type="DIALOGUE", game_time_ms=2000 + (24 * MS_PER_HOUR)),
            Event(type="DEATH", game_time_ms=2000),
        ]
        
        result = inject_time_gaps(events, last_update_time_ms=0)
        
        # Should be sorted: DEATH, NarrativeCue, DIALOGUE
        assert result[0].type == "DEATH"
        assert isinstance(result[1], NarrativeCue)
        assert result[1].type == "TIME_GAP"
        assert result[2].type == "DIALOGUE"
    
    def test_narrative_cue_message_format(self):
        """NarrativeCue message is properly formatted."""
        MS_PER_HOUR = 60 * 60 * 1000
        events = [Event(type="DEATH", game_time_ms=1000 + (15 * MS_PER_HOUR))]
        
        result = inject_time_gaps(events, last_update_time_ms=1000)
        cue = result[0]
        
        assert isinstance(cue, NarrativeCue)
        assert cue.message == "TIME GAP: Approximately 15 hours have passed since the last event."
    
    def test_narrative_cue_is_cue_property(self):
        """NarrativeCue has is_cue property that returns True."""
        cue = NarrativeCue(
            type="TIME_GAP",
            message="TIME GAP: Approximately 12 hours have passed since the last event.",
            game_time_ms=5000,
        )
        
        assert cue.is_cue is True
        assert cue.type == "TIME_GAP"
        assert "12 hours" in cue.message


# ---------------------------------------------------------------------------
# build_dialogue_user_message tests
# ---------------------------------------------------------------------------

from talker_service.prompts.dialogue import build_dialogue_user_message


class TestBuildDialogueUserMessage:
    """Tests for the inline dialogue user message builder."""

    def test_with_narrative(self):
        msg = build_dialogue_user_message(
            speaker_name="Wolf",
            speaker_id="12467",
            event_description="A mutant attacked the nearby camp.",
            narrative="[SUMMARIES] Wolf recalls a patrol.",
        )
        assert "A mutant attacked the nearby camp." in msg
        assert "Wolf" in msg
        assert "12467" in msg
        assert "Personal memories:" in msg
        assert "[SUMMARIES] Wolf recalls a patrol." in msg
        assert "just the spoken words" in msg

    def test_without_narrative(self):
        msg = build_dialogue_user_message(
            speaker_name="Nobody",
            speaker_id="99",
            event_description="Something happened.",
            narrative="",
        )
        assert "Something happened." in msg
        assert "Nobody" in msg
        assert "99" in msg
        assert "Personal memories:" not in msg
        assert "just the spoken words" in msg

    def test_includes_dynamic_world_line(self):
        msg = build_dialogue_user_message(
            speaker_name="Wolf",
            speaker_id="12467",
            event_description="An emission approaches.",
            narrative="",
            dynamic_world_line="Weather: Clear | Time: 14:30 | Location: Rostok",
        )
        assert "Weather: Clear" in msg
        assert "An emission approaches." in msg

    def test_includes_witness_text(self):
        msg = build_dialogue_user_message(
            speaker_name="Wolf",
            speaker_id="12467",
            event_description="A bandit attack.",
            narrative="",
            witness_text="A patrol was ambushed nearby.",
        )
        assert "Recent events witnessed by Wolf:" in msg
        assert "A patrol was ambushed nearby." in msg

    def test_no_dynamic_world_line_when_empty(self):
        msg = build_dialogue_user_message(
            speaker_name="Wolf",
            speaker_id="12467",
            event_description="Event text.",
            narrative="",
            dynamic_world_line="",
        )
        # First line should be the event description, no empty line before
        assert msg.startswith("Event text.")
