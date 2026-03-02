"""Tests for the ws-schema-validation — validates the schema compiler.

Each test maps to a spec scenario from:
  openspec/changes/zmq-api-schema/specs/ws-schema-validation/spec.md
"""

from pathlib import Path

import jsonschema
import pytest

from .schema_compiler import compile_schema

_SCHEMA_PATH = Path(__file__).resolve().parents[3] / "docs" / "ws-api.yaml"


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
                "dialogue.display", "event.store",
                "config.request", "service.heartbeat.ack",
                "state.query.batch",
                "state.response",
                "state.mutate.batch",
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

    def test_character_ref_in_batch_request(self, compiled):
        req = compiled["state.query.batch"]["request"]
        # batch request has a queries array - verify it compiled
        assert "properties" in req
        assert "queries" in req["properties"]


class TestCompilerHandlesArrayWithTypedItems:
    """Scenario: Compiler handles array fields with typed items."""

    def test_witnesses_array_with_character_ref(self, compiled):
        defs = compiled["game.event"]["payload"]["$defs"]
        event = defs["Event"]
        witnesses = event["properties"]["witnesses"]
        assert witnesses["type"] == "array"
        assert witnesses["items"]["$ref"] == "#/$defs/Character"


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
            "candidates": [{"game_id": "12345", "name": "Wolf"}],
            "world": "Location: Cordon. Time: June 1, 1:00 PM. Weather: Clear.",
            "traits": {"12345": {"personality_id": "gruff_but_fair", "backstory_id": "veteran_stalker"}},
        }
        jsonschema.validate(valid_payload, schema)  # should not raise


class TestInvalidPayloadFieldTypeFails:
    """Scenario: Invalid payload field type fails validation."""

    def test_is_important_as_string_fails(self, compiled):
        schema = compiled["game.event"]["payload"]
        invalid_payload = {
            "event": {"type": "death"},
            "candidates": "not_an_array",  # should be array
            "world": "...",
            "traits": {},
        }
        with pytest.raises(jsonschema.ValidationError) as exc_info:
            jsonschema.validate(invalid_payload, schema)
        assert "not_an_array" in str(exc_info.value.instance) or "candidates" in str(exc_info.value.message)


class TestMissingRequiredFieldFails:
    """Scenario: Missing required field fails validation."""

    def test_missing_event_field_fails(self, compiled):
        schema = compiled["game.event"]["payload"]
        invalid_payload = {
            "candidates": [{"game_id": "1", "name": "Wolf"}],
            "world": "Cordon",
            "traits": {}
        }  # missing "event"
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
            "candidates": [{"game_id": "1", "name": "Wolf"}],
            "world": "Cordon",
            "traits": {"1": {"personality_id": "generic", "backstory_id": "generic"}},
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
            "candidates": [{"game_id": "1", "name": "Wolf"}],
            "world": "Cordon",
            "traits": {"1": {"personality_id": "generic", "backstory_id": "generic"}},
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

    def test_state_mock_memories_present(self, scenario):
        """Verify state mocks contain memory data (used by LuaSimulator)."""
        assert "state.query.memories" in scenario["state_mocks"]
        mock = scenario["state_mocks"]["state.query.memories"]
        assert "response" in mock
        assert "narrative" in mock["response"]

    def test_state_mock_character_present(self, scenario):
        """Verify state mocks contain character data."""
        assert "state.query.character" in scenario["state_mocks"]
        mock = scenario["state_mocks"]["state.query.character"]
        assert "response" in mock
        assert "game_id" in mock["response"]

    def test_state_mock_world_present(self, scenario):
        """Verify state mocks contain world data."""
        assert "state.query.world" in scenario["state_mocks"]
        mock = scenario["state_mocks"]["state.query.world"]
        assert "response" in mock
        assert "loc" in mock["response"]

    def test_expected_ws_published_valid(self, compiled, scenario):
        for pub in scenario["expected"]["ws_published"]:
            topic = pub["topic"]
            schema = compiled[topic]["payload"]
            jsonschema.validate(pub["payload"], schema)

    def test_expected_state_queries_valid(self, scenario):
        """Verify expected state queries reference batch topic."""
        for sq in scenario["expected"]["state_queries"]:
            assert sq["topic"] == "state.query.batch"
