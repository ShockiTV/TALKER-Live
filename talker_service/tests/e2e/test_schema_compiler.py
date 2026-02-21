"""Tests for the zmq-schema-validation spec — validates the schema compiler.

Each test maps to a spec scenario from:
  openspec/changes/zmq-api-schema/specs/zmq-schema-validation/spec.md
"""

from pathlib import Path

import jsonschema
import pytest

from .schema_compiler import compile_schema

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "docs" / "zmq-api.yaml"


@pytest.fixture(scope="module")
def compiled() -> dict:
    """Compile the schema once for the whole module."""
    return compile_schema(str(_SCHEMA_PATH))


# ── Requirement: Schema compiler module ──────────────────────


class TestCompilerProducesValidJsonSchema:
    """Scenario: Compiler produces valid JSON Schema for a message."""

    def test_game_event_entry_exists(self, compiled):
        assert "game.event" in compiled

    def test_game_event_has_payload_key(self, compiled):
        assert "payload" in compiled["game.event"]

    def test_game_event_payload_has_defs(self, compiled):
        payload_schema = compiled["game.event"]["payload"]
        assert "$defs" in payload_schema
        assert "Event" in payload_schema["$defs"]
        assert "Character" in payload_schema["$defs"]

    def test_all_topics_present(self, compiled):
        expected = [
            "game.event", "player.dialogue", "player.whisper",
            "config.update", "config.sync", "system.heartbeat",
            "dialogue.display", "memory.update", "event.store",
            "config.request", "service.heartbeat.ack",
            "state.query.memories", "state.query.events",
            "state.query.character", "state.query.characters_nearby",
            "state.query.characters_alive", "state.query.world",
            "state.response",
        ]
        for topic in expected:
            assert topic in compiled, f"Missing compiled topic: {topic}"


class TestCompilerMapsTypesToDefs:
    """Scenario: Compiler maps custom types to JSON Schema $defs."""

    def test_character_game_id_in_properties(self, compiled):
        defs = compiled["game.event"]["payload"]["$defs"]
        char = defs["Character"]
        assert "game_id" in char["properties"]

    def test_character_game_id_in_required(self, compiled):
        defs = compiled["game.event"]["payload"]["$defs"]
        char = defs["Character"]
        assert "game_id" in char.get("required", [])

    def test_character_name_in_required(self, compiled):
        defs = compiled["game.event"]["payload"]["$defs"]
        char = defs["Character"]
        assert "name" in char.get("required", [])


class TestCompilerHandlesRef:
    """Scenario: Compiler handles $ref fields."""

    def test_event_ref_in_game_event_payload(self, compiled):
        props = compiled["game.event"]["payload"]["properties"]
        event_prop = props["event"]
        # May be wrapped in allOf for description
        if "allOf" in event_prop:
            refs = [x.get("$ref") for x in event_prop["allOf"] if "$ref" in x]
            assert "#/$defs/Event" in refs
        else:
            assert event_prop.get("$ref") == "#/$defs/Event"

    def test_character_ref_in_memory_response(self, compiled):
        resp = compiled["state.query.character"]["response"]
        char_prop = resp["properties"]["character"]
        if "allOf" in char_prop:
            refs = [x.get("$ref") for x in char_prop["allOf"] if "$ref" in x]
            assert "#/$defs/Character" in refs
        else:
            assert char_prop.get("$ref") == "#/$defs/Character"


class TestCompilerHandlesArrayWithTypedItems:
    """Scenario: Compiler handles array fields with typed items."""

    def test_witnesses_array_with_character_ref(self, compiled):
        defs = compiled["game.event"]["payload"]["$defs"]
        event = defs["Event"]
        witnesses = event["properties"]["witnesses"]
        assert witnesses["type"] == "array"
        assert witnesses["items"]["$ref"] == "#/$defs/Character"

    def test_new_events_array_with_event_ref(self, compiled):
        resp = compiled["state.query.memories"]["response"]
        new_events = resp["properties"]["new_events"]
        assert new_events["type"] == "array"
        assert new_events["items"]["$ref"] == "#/$defs/Event"


class TestCompilerAdditionalProperties:
    """All compiled schemas allow additional properties."""

    def test_payload_allows_additional(self, compiled):
        schema = compiled["game.event"]["payload"]
        assert schema.get("additionalProperties") is True

    def test_defs_types_allow_additional(self, compiled):
        defs = compiled["game.event"]["payload"]["$defs"]
        for type_name, type_schema in defs.items():
            if type_schema.get("type") == "object":
                assert type_schema.get("additionalProperties") is True, (
                    f"$defs.{type_name} should allow additionalProperties"
                )


# ── Requirement: Scenario payload validation at collection time ──


class TestValidScenarioPasses:
    """Scenario: Valid scenario passes schema validation."""

    def test_valid_game_event_payload(self, compiled):
        schema = compiled["game.event"]["payload"]
        valid_payload = {
            "event": {
                "type": "death",
                "context": {"killer": {"game_id": "1", "name": "Wolf"}},
                "game_time_ms": 1000,
                "witnesses": [],
                "flags": {},
            },
            "is_important": True,
        }
        jsonschema.validate(valid_payload, schema)  # should not raise


class TestInvalidPayloadFieldTypeFails:
    """Scenario: Invalid payload field type fails validation."""

    def test_is_important_as_string_fails(self, compiled):
        schema = compiled["game.event"]["payload"]
        invalid_payload = {
            "event": {"type": "death"},
            "is_important": "yes",  # should be bool
        }
        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(invalid_payload, schema)
        assert "yes" in str(exc_info.value.message)


class TestMissingRequiredFieldFails:
    """Scenario: Missing required field fails validation."""

    def test_missing_event_field_fails(self, compiled):
        schema = compiled["game.event"]["payload"]
        invalid_payload = {"is_important": False}  # missing "event"
        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(invalid_payload, schema)
        assert "event" in str(exc_info.value.message)

    def test_missing_event_type_fails(self, compiled):
        schema = compiled["game.event"]["payload"]
        invalid_payload = {"event": {"context": {}}}  # missing "type" in event
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(invalid_payload, schema)


class TestExtraFieldsTolerated:
    """Scenario: Validation is tolerant of extra fields."""

    def test_extra_top_level_field_allowed(self, compiled):
        schema = compiled["game.event"]["payload"]
        payload = {
            "event": {"type": "death"},
            "is_important": True,
            "extra_field": "should be ignored",
        }
        jsonschema.validate(payload, schema)  # should not raise

    def test_extra_nested_field_allowed(self, compiled):
        schema = compiled["game.event"]["payload"]
        payload = {
            "event": {
                "type": "death",
                "context": {"custom_field": "allowed"},
                "future_field": 42,
            },
        }
        jsonschema.validate(payload, schema)  # should not raise


class TestInvalidEventTypeEnumFails:
    """Validate that invalid enum values are rejected."""

    def test_uppercase_event_type_rejected(self, compiled):
        schema = compiled["game.event"]["payload"]
        payload = {"event": {"type": "DEATH"}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, schema)

    def test_unknown_event_type_rejected(self, compiled):
        schema = compiled["game.event"]["payload"]
        payload = {"event": {"type": "explosion"}}
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(payload, schema)


# ── Requirement: jsonschema dependency ───────────────────────


class TestJsonschemaDependency:
    """Scenario: jsonschema is available in dev environment."""

    def test_import_jsonschema(self):
        import jsonschema as js
        assert hasattr(js, "validate")

    def test_import_pyyaml(self):
        import yaml as y
        assert hasattr(y, "safe_load")


# ── Validate real scenario file against compiled schema ──────


class TestDeathWolfFullScenario:
    """Validate the real death_wolf_full.json scenario passes all schema checks."""

    @pytest.fixture(scope="class")
    def scenario(self):
        import json
        path = Path(__file__).parent / "scenarios" / "death_wolf_full.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_input_payload_valid(self, compiled, scenario):
        topic = scenario["input"]["topic"]
        schema = compiled[topic]["payload"]
        jsonschema.validate(scenario["input"]["payload"], schema)

    def test_state_mock_memories_valid(self, compiled, scenario):
        mock = scenario["state_mocks"]["state.query.memories"]
        schema = compiled["state.query.memories"]["response"]
        jsonschema.validate(mock["response"], schema)

    def test_state_mock_character_valid(self, compiled, scenario):
        mock = scenario["state_mocks"]["state.query.character"]
        schema = compiled["state.query.character"]["response"]
        jsonschema.validate(mock["response"], schema)

    def test_state_mock_world_valid(self, compiled, scenario):
        mock = scenario["state_mocks"]["state.query.world"]
        schema = compiled["state.query.world"]["response"]
        jsonschema.validate(mock["response"], schema)

    def test_expected_zmq_published_valid(self, compiled, scenario):
        for pub in scenario["expected"]["zmq_published"]:
            topic = pub["topic"]
            schema = compiled[topic]["payload"]
            jsonschema.validate(pub["payload"], schema)

    def test_expected_state_queries_valid(self, compiled, scenario):
        for sq in scenario["expected"]["state_queries"]:
            topic = sq["topic"]
            if topic in compiled and "request" in compiled[topic]:
                schema = compiled[topic]["request"]
                jsonschema.validate(sq["payload"], schema)
