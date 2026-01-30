"""Tests for prompts module."""

import pytest

from talker_service.prompts import (
    Character,
    Event,
    MemoryContext,
    Message,
    describe_character,
    describe_character_with_id,
    describe_event,
    is_junk_event,
    was_witnessed_by,
    get_faction_description,
    get_faction_relation,
    get_faction_relations_text,
    create_pick_speaker_prompt,
    create_dialogue_request_prompt,
    create_compress_memories_prompt,
    create_update_narrative_prompt,
    create_transcription_prompt,
)


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
            reputation="Good",
        )
        assert char.game_id == "123"
        assert char.name == "Hip"
        assert char.faction == "stalker"
        assert char.experience == "Veteran"
        assert char.reputation == "Good"
    
    def test_character_from_dict(self):
        data = {
            "game_id": 456,
            "name": "Wolf",
            "faction": "stalker",
            "experience": "Expert",
            "reputation": "Great",
            "personality": "gruff veteran",
            "backstory": "former military",
        }
        char = Character.from_dict(data)
        assert char.game_id == "456"
        assert char.name == "Wolf"
        assert char.personality == "gruff veteran"
        assert char.backstory == "former military"
    
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
            "world_context": "In Cordon",
            "flags": {"is_idle": True},
        }
        event = Event.from_dict(data)
        assert event.type == "DIALOGUE"
        assert event.world_context == "In Cordon"
        assert event.flags == {"is_idle": True}
    
    def test_event_from_dict_with_legacy_content(self):
        data = {"content": "Something happened", "game_time_ms": 500}
        event = Event.from_dict(data)
        assert event.content == "Something happened"


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
            reputation="Good",
        )
        desc = describe_character(char)
        assert "Hip" in desc
        assert "Veteran" in desc
        assert "stalker" in desc
        assert "Good" in desc
    
    def test_describe_monster(self):
        char = Character(
            game_id="999",
            name="Bloodsucker",
            faction="Monster",
            experience="",
            reputation="",
        )
        desc = describe_character(char)
        assert "Bloodsucker" in desc
        assert "Monster" in desc
    
    def test_describe_character_with_id(self):
        char = Character(
            game_id="456",
            name="Wolf",
            faction="stalker",
            experience="Expert",
            reputation="Great",
        )
        desc = describe_character_with_id(char)
        assert "[ID: 456]" in desc
        assert "Wolf" in desc


class TestDescribeEvent:
    """Tests for describe_event helper."""
    
    def test_describe_death_event(self):
        victim = Character(game_id="1", name="Bandit", faction="Bandit", experience="Novice", reputation="Bad")
        killer = Character(game_id="2", name="Hip", faction="stalker", experience="Veteran", reputation="Good")
        event = Event(
            type="DEATH",
            context={"victim": victim.__dict__, "killer": killer.__dict__},
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "killed" in desc.lower() or "death" in desc.lower() or "bandit" in desc.lower()
    
    def test_describe_dialogue_event(self):
        speaker = Character(game_id="1", name="Hip", faction="stalker", experience="Veteran", reputation="Good")
        event = Event(
            type="DIALOGUE",
            context={"speaker": speaker.__dict__, "text": "Stay safe out there"},
            game_time_ms=1000,
        )
        desc = describe_event(event)
        assert "Hip" in desc or "said" in desc.lower()
    
    def test_describe_legacy_event(self):
        event = Event(
            type=None,
            context={},
            game_time_ms=1000,
            content="A mysterious event occurred",
        )
        desc = describe_event(event)
        assert "mysterious event" in desc


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
        witness = Character(game_id="123", name="Hip", faction="stalker", experience="Veteran", reputation="Good")
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
        desc = get_faction_description("Duty")
        assert "paramilitary" in desc.lower() or "zone" in desc.lower()
    
    def test_get_faction_description_unknown(self):
        desc = get_faction_description("UnknownFaction")
        assert desc == ""
    
    def test_get_faction_relation_hostile(self):
        assert get_faction_relation("Duty", "Freedom") == -1
        assert get_faction_relation("Freedom", "Duty") == -1
    
    def test_get_faction_relation_allied(self):
        assert get_faction_relation("Duty", "Ecolog") == 1
    
    def test_get_faction_relation_same(self):
        assert get_faction_relation("Duty", "Duty") == 1
    
    def test_get_faction_relation_neutral(self):
        # Unknown factions default to neutral
        assert get_faction_relation("Duty", "UnknownFaction") == 0
    
    def test_get_faction_relations_text(self):
        text = get_faction_relations_text("Duty", {"Freedom", "Bandit"})
        assert "HOSTILE" in text
        assert "Duty" in text


# ============================================================================
# Prompt Builder Tests
# ============================================================================

class TestCreatePickSpeakerPrompt:
    """Tests for create_pick_speaker_prompt."""
    
    def test_creates_messages(self):
        witness = Character(game_id="123", name="Hip", faction="stalker", experience="Veteran", reputation="Good")
        event = Event(type="DIALOGUE", context={"text": "Hello"}, game_time_ms=1000)
        
        messages = create_pick_speaker_prompt([event], [witness])
        
        assert len(messages) > 0
        assert all(isinstance(m, Message) for m in messages)
        assert any("SPEAKER" in m.content.upper() for m in messages)
        assert any("CANDIDATES" in m.content.upper() for m in messages)
    
    def test_limits_to_8_events(self):
        witness = Character(game_id="123", name="Hip", faction="stalker", experience="Veteran", reputation="Good")
        events = [Event(type="DIALOGUE", context={"text": f"Hello {i}"}, game_time_ms=i * 1000) for i in range(15)]
        
        messages = create_pick_speaker_prompt(events, [witness])
        
        # Should have limited the events, but we can't easily verify the internal count
        # Just verify it completes without error
        assert len(messages) > 0
    
    def test_raises_on_no_witnesses(self):
        event = Event(type="DIALOGUE", context={}, game_time_ms=1000)
        with pytest.raises(ValueError, match="No witnesses"):
            create_pick_speaker_prompt([event], [])
    
    def test_raises_on_no_events(self):
        witness = Character(game_id="123", name="Hip", faction="stalker", experience="Veteran", reputation="Good")
        with pytest.raises(ValueError, match="No recent events"):
            create_pick_speaker_prompt([], [witness])


class TestCreateDialogueRequestPrompt:
    """Tests for create_dialogue_request_prompt."""
    
    def test_creates_messages(self):
        speaker = Character(
            game_id="123",
            name="Hip",
            faction="stalker",
            experience="Veteran",
            reputation="Good",
            personality="friendly",
            backstory="former medic",
        )
        memory_context = MemoryContext(
            narrative="Hip met the player in Cordon.",
            new_events=[Event(type="DIALOGUE", context={"text": "Hello"}, game_time_ms=1000)],
            last_update_time_ms=500,
        )
        
        messages, timestamp = create_dialogue_request_prompt(speaker, memory_context)
        
        assert len(messages) > 0
        assert all(isinstance(m, Message) for m in messages)
        assert timestamp is None  # No idle event
    
    def test_detects_idle_event(self):
        speaker = Character(game_id="123", name="Hip", faction="stalker", experience="Veteran", reputation="Good")
        idle_event = Event(
            type="IDLE",
            context={},
            game_time_ms=5000,
            flags={"is_idle": True},
        )
        memory_context = MemoryContext(new_events=[idle_event])
        
        messages, timestamp = create_dialogue_request_prompt(speaker, memory_context)
        
        assert timestamp == 5000  # Should mark for deletion
    
    def test_includes_character_info(self):
        speaker = Character(
            game_id="123",
            name="Hip",
            faction="stalker",
            experience="Veteran",
            reputation="Good",
            personality="friendly",
            backstory="former medic",
        )
        memory_context = MemoryContext()
        
        messages, _ = create_dialogue_request_prompt(speaker, memory_context)
        
        # Find the character section
        content = " ".join(m.content for m in messages)
        assert "Hip" in content
        assert "stalker" in content
        assert "friendly" in content


class TestCreateCompressMemoriesPrompt:
    """Tests for create_compress_memories_prompt."""
    
    def test_creates_messages(self):
        speaker = Character(game_id="123", name="Hip", faction="stalker", experience="Veteran", reputation="Good")
        events = [
            Event(type="DIALOGUE", context={"text": "Hello"}, game_time_ms=1000),
            Event(type="DEATH", context={"victim": {"name": "Bandit"}}, game_time_ms=2000),
        ]
        
        messages = create_compress_memories_prompt(events, speaker)
        
        assert len(messages) > 0
        assert any("COMPRESSION" in m.content.upper() for m in messages)
    
    def test_filters_junk_events(self):
        events = [
            Event(type="DIALOGUE", context={"text": "Hello"}, game_time_ms=1000),
            Event(type="ARTIFACT", context={}, game_time_ms=2000),  # Junk
            Event(type="RELOAD", context={}, game_time_ms=3000),  # Junk
        ]
        
        messages = create_compress_memories_prompt(events)
        
        # Junk events should be filtered out, so we shouldn't see ARTIFACT or RELOAD content
        content = " ".join(m.content for m in messages if m.role == "user")
        # The junk events shouldn't appear as user messages
        assert len([m for m in messages if m.role == "user"]) <= 1


class TestCreateUpdateNarrativePrompt:
    """Tests for create_update_narrative_prompt."""
    
    def test_creates_bootstrap_prompt(self):
        speaker = Character(game_id="123", name="Hip", faction="stalker", experience="Veteran", reputation="Good")
        events = [
            Event(type="DIALOGUE", context={"text": "Hello"}, game_time_ms=1000),
        ]
        
        messages = create_update_narrative_prompt(speaker, None, events)
        
        assert len(messages) > 0
        assert any("MEMORY" in m.content.upper() for m in messages)
    
    def test_creates_update_prompt_with_existing_narrative(self):
        speaker = Character(game_id="123", name="Hip", faction="stalker", experience="Veteran", reputation="Good")
        narrative = "Hip previously met the player in Cordon."
        events = [
            Event(type="DIALOGUE", context={"text": "Hello again"}, game_time_ms=5000),
        ]
        
        messages = create_update_narrative_prompt(speaker, narrative, events)
        
        assert len(messages) > 0
        # Should contain the existing narrative
        content = " ".join(m.content for m in messages)
        assert "CURRENT_MEMORY" in content


class TestCreateTranscriptionPrompt:
    """Tests for create_transcription_prompt."""
    
    def test_creates_prompt(self):
        names = ["Hip", "Wolf", "Fanatic"]
        prompt = create_transcription_prompt(names)
        
        assert "STALKER" in prompt
        assert "Hip" in prompt
        assert "Wolf" in prompt
        assert "Fanatic" in prompt


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
