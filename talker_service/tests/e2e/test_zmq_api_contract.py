"""Tests for the zmq-api-contract spec — validates docs/zmq-api.yaml content.

Each test maps to a spec scenario from:
  openspec/changes/zmq-api-schema/specs/zmq-api-contract/spec.md
"""

from pathlib import Path

import pytest
import yaml

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "docs" / "zmq-api.yaml"


@pytest.fixture(scope="module")
def schema() -> dict:
    """Load and parse docs/zmq-api.yaml once for the whole module."""
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def types(schema) -> dict:
    return schema["types"]


@pytest.fixture(scope="module")
def messages(schema) -> dict:
    return schema["messages"]


# ── Requirement: YAML schema file at docs/zmq-api.yaml ───────


class TestSchemaFileStructure:
    """Scenario: Schema file exists and is valid YAML."""

    def test_schema_file_exists(self):
        assert _SCHEMA_PATH.exists(), f"{_SCHEMA_PATH} does not exist"

    def test_schema_parses_without_errors(self, schema):
        assert isinstance(schema, dict)

    @pytest.mark.parametrize("key", ["version", "wire_format", "types", "messages"])
    def test_schema_has_top_level_key(self, schema, key):
        assert key in schema, f"Missing top-level key: {key}"


# ── Requirement: Shared type definitions ──────────────────────


class TestCharacterType:
    """Scenario: Character type defines all fields from both codebases."""

    REQUIRED_FIELDS = ["game_id", "name"]
    OPTIONAL_FIELDS = [
        "faction", "experience", "reputation", "personality",
        "backstory", "weapon", "visual_faction", "story_id",
    ]

    def test_character_type_exists(self, types):
        assert "Character" in types

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_character_required_field_present(self, types, field):
        assert field in types["Character"]

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_character_required_field_is_required(self, types, field):
        assert types["Character"][field].get("required") is True

    @pytest.mark.parametrize("field", OPTIONAL_FIELDS)
    def test_character_optional_field_present(self, types, field):
        assert field in types["Character"]


class TestEventType:
    """Scenario: Event type matches typed event structure."""

    EXPECTED_ENUM = [
        "death", "dialogue", "callout", "taunt", "artifact", "anomaly",
        "map_transition", "emission", "injury", "sleep", "task",
        "weapon_jam", "reload", "idle",
    ]

    def test_event_type_exists(self, types):
        assert "Event" in types

    def test_event_type_field_has_enum(self, types):
        type_field = types["Event"]["type"]
        assert "enum" in type_field
        assert set(self.EXPECTED_ENUM) == set(type_field["enum"])

    def test_event_type_field_is_required(self, types):
        assert types["Event"]["type"].get("required") is True

    def test_event_context_ref(self, types):
        assert types["Event"]["context"]["$ref"] == "EventContext"

    def test_event_game_time_ms(self, types):
        assert types["Event"]["game_time_ms"]["type"] == "int"

    def test_event_witnesses_array_of_character(self, types):
        w = types["Event"]["witnesses"]
        assert w["type"] == "array"
        assert w["items"]["$ref"] == "Character"

    def test_event_flags_ref(self, types):
        assert types["Event"]["flags"]["$ref"] == "EventFlags"


class TestEventFlagsType:
    """EventFlags type has all required flag fields."""

    @pytest.mark.parametrize("field", ["is_silent", "is_idle", "is_compressed", "is_synthetic"])
    def test_flag_field_present(self, types, field):
        assert field in types["EventFlags"]
        assert types["EventFlags"][field]["type"] == "bool"


class TestEventContextType:
    """EventContext type has all spec-required fields."""

    REQUIRED_FIELDS = [
        "actor", "victim", "killer", "spotter", "target", "taunter", "speaker",
        "text", "item_name", "action", "health_percent", "from_location",
        "to_location", "companions", "task_name",
    ]

    @pytest.mark.parametrize("field", REQUIRED_FIELDS)
    def test_event_context_field_present(self, types, field):
        assert field in types["EventContext"], f"EventContext missing field: {field}"


# ── Requirement: Lua→Python message definitions ──────────────


class TestLuaToPythonMessages:
    """All Lua→Python topics present with correct direction."""

    TOPICS = [
        "game.event", "player.dialogue", "player.whisper",
        "config.update", "config.sync", "system.heartbeat",
    ]

    @pytest.mark.parametrize("topic", TOPICS)
    def test_topic_exists(self, messages, topic):
        assert topic in messages

    @pytest.mark.parametrize("topic", TOPICS)
    def test_direction_lua_to_python(self, messages, topic):
        assert messages[topic]["direction"] == "lua→python"

    @pytest.mark.parametrize("topic", TOPICS)
    def test_has_payload(self, messages, topic):
        assert "payload" in messages[topic]


class TestGameEventMessage:
    """Scenario: game.event message is fully defined."""

    def test_direction(self, messages):
        assert messages["game.event"]["direction"] == "lua→python"

    def test_event_ref_required(self, messages):
        payload = messages["game.event"]["payload"]
        assert payload["event"]["$ref"] == "Event"
        assert payload["event"].get("required") is True

    def test_is_important_bool_default_false(self, messages):
        field = messages["game.event"]["payload"]["is_important"]
        assert field["type"] == "bool"
        assert field["default"] is False


class TestPlayerDialogueMessage:
    """Scenario: player.dialogue message is fully defined."""

    def test_text_required(self, messages):
        field = messages["player.dialogue"]["payload"]["text"]
        assert field["type"] == "string"
        assert field.get("required") is True

    def test_context_optional(self, messages):
        field = messages["player.dialogue"]["payload"]["context"]
        assert field["type"] == "object"
        assert field.get("required") is not True


class TestSystemHeartbeatMessage:
    """Scenario: system.heartbeat message is fully defined."""

    def test_game_time_ms(self, messages):
        assert messages["system.heartbeat"]["payload"]["game_time_ms"]["type"] == "int"

    def test_status(self, messages):
        field = messages["system.heartbeat"]["payload"]["status"]
        assert field["type"] == "string"


# ── Requirement: Python→Lua command definitions ──────────────


class TestPythonToLuaMessages:
    """All Python→Lua topics present with correct direction."""

    TOPICS = [
        "dialogue.display", "memory.update", "event.store",
        "config.request", "service.heartbeat.ack",
    ]

    @pytest.mark.parametrize("topic", TOPICS)
    def test_topic_exists(self, messages, topic):
        assert topic in messages

    @pytest.mark.parametrize("topic", TOPICS)
    def test_direction_python_to_lua(self, messages, topic):
        assert messages[topic]["direction"] == "python→lua"


class TestDialogueDisplayMessage:
    """Scenario: dialogue.display message is fully defined."""

    def test_direction(self, messages):
        assert messages["dialogue.display"]["direction"] == "python→lua"

    def test_speaker_id_required(self, messages):
        field = messages["dialogue.display"]["payload"]["speaker_id"]
        assert field["type"] == "string"
        assert field.get("required") is True

    def test_dialogue_required(self, messages):
        field = messages["dialogue.display"]["payload"]["dialogue"]
        assert field["type"] == "string"
        assert field.get("required") is True

    def test_create_event_bool_default_true(self, messages):
        field = messages["dialogue.display"]["payload"]["create_event"]
        assert field["type"] == "bool"
        assert field["default"] is True

    def test_event_context_optional(self, messages):
        field = messages["dialogue.display"]["payload"]["event_context"]
        assert field["type"] == "object"
        assert field.get("required") is not True


class TestMemoryUpdateMessage:
    """Scenario: memory.update message is fully defined."""

    def test_character_id_required(self, messages):
        field = messages["memory.update"]["payload"]["character_id"]
        assert field["type"] == "string"
        assert field.get("required") is True

    def test_narrative_optional(self, messages):
        field = messages["memory.update"]["payload"]["narrative"]
        assert field["type"] == "string"
        assert field.get("required") is not True

    def test_last_event_time_ms_optional(self, messages):
        field = messages["memory.update"]["payload"]["last_event_time_ms"]
        assert field["type"] == "int"
        assert field.get("required") is not True


# ── Requirement: State query definitions ─────────────────────


class TestStateQueryTopics:
    """All state query topics present with correct direction."""

    TOPICS = [
        "state.query.memories", "state.query.events",
        "state.query.character", "state.query.characters_nearby",
        "state.query.characters_alive", "state.query.world",
    ]

    @pytest.mark.parametrize("topic", TOPICS)
    def test_topic_exists(self, messages, topic):
        assert topic in messages

    @pytest.mark.parametrize("topic", TOPICS)
    def test_direction_bidirectional(self, messages, topic):
        assert messages[topic]["direction"] == "python→lua→python"

    @pytest.mark.parametrize("topic", TOPICS)
    def test_has_request_and_response(self, messages, topic):
        assert "request" in messages[topic]
        assert "response" in messages[topic]


class TestStateQueryMemories:
    """Scenario: state.query.memories is fully defined."""

    def test_request_character_id_required(self, messages):
        field = messages["state.query.memories"]["request"]["character_id"]
        assert field["type"] == "string"
        assert field.get("required") is True

    def test_response_character_id(self, messages):
        resp = messages["state.query.memories"]["response"]
        assert "character_id" in resp

    def test_response_narrative(self, messages):
        resp = messages["state.query.memories"]["response"]
        assert resp["narrative"]["type"] == "string"

    def test_response_last_update_time_ms(self, messages):
        resp = messages["state.query.memories"]["response"]
        assert resp["last_update_time_ms"]["type"] == "int"

    def test_response_new_events_array_of_event(self, messages):
        field = messages["state.query.memories"]["response"]["new_events"]
        assert field["type"] == "array"
        assert field["items"]["$ref"] == "Event"


class TestStateQueryWorld:
    """Scenario: state.query.world is fully defined."""

    def test_request_empty(self, messages):
        req = messages["state.query.world"]["request"]
        assert req == {} or req is None or len(req) == 0

    def test_response_references_scene_context(self, messages):
        resp = messages["state.query.world"]["response"]
        assert resp.get("$ref") == "SceneContext"

    def test_scene_context_has_all_fields(self, types):
        sc = types["SceneContext"]
        for field in ["loc", "time", "weather", "emission", "psy_storm",
                       "sheltering", "campfire", "brain_scorcher_disabled",
                       "miracle_machine_disabled"]:
            assert field in sc, f"SceneContext missing field: {field}"

    def test_campfire_is_nullable(self, types):
        assert types["SceneContext"]["campfire"].get("nullable") is True


class TestStateQueryCharactersAlive:
    """Scenario: state.query.characters_alive is fully defined."""

    def test_request_ids_required(self, messages):
        field = messages["state.query.characters_alive"]["request"]["ids"]
        assert field["type"] == "array"
        assert field["items"]["type"] == "string"
        assert field.get("required") is True

    def test_response_is_flat_object(self, messages):
        resp = messages["state.query.characters_alive"]["response"]
        assert resp.get("type") == "object"


# ── Requirement: state.response envelope ─────────────────────


class TestStateResponseEnvelope:
    """Scenario: state.response envelope is documented."""

    def test_direction(self, messages):
        assert messages["state.response"]["direction"] == "lua→python"

    def test_request_id_required(self, messages):
        field = messages["state.response"]["payload"]["request_id"]
        assert field["type"] == "string"
        assert field.get("required") is True

    def test_response_type_present(self, messages):
        assert "response_type" in messages["state.response"]["payload"]

    def test_data_present(self, messages):
        field = messages["state.response"]["payload"]["data"]
        assert field["type"] == "object"

    def test_error_present(self, messages):
        field = messages["state.response"]["payload"]["error"]
        assert field["type"] == "string"


# ── Requirement: Lua empty table handling note ───────────────


class TestEmptyTableHandlingNote:
    """Scenario: Empty table handling is documented."""

    def test_notes_section_exists(self, schema):
        assert "notes" in schema

    def test_lua_empty_tables_note_exists(self, schema):
        assert "lua_empty_tables" in schema["notes"]

    def test_note_mentions_empty_tables(self, schema):
        note = schema["notes"]["lua_empty_tables"]
        assert "empty" in note.lower() or "{}" in note
        assert "[]" in note


# ── Requirement: docs/ZMQ_Message_Schema.md is removed ──────


class TestOldMarkdownRemoved:
    """Scenario: Old markdown file does not exist."""

    def test_old_markdown_deleted(self):
        old_path = _SCHEMA_PATH.parent / "ZMQ_Message_Schema.md"
        assert not old_path.exists(), f"{old_path} should have been deleted"
