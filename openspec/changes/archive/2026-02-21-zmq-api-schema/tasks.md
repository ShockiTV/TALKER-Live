## 1. Dependencies

- [x] 1.1 Add `jsonschema>=4.0.0` and `pyyaml>=6.0` to `[project.optional-dependencies] dev` in `talker_service/pyproject.toml`
- [x] 1.2 Install updated dev dependencies into the venv

## 2. YAML Schema File

- [x] 2.1 Create `docs/zmq-api.yaml` with `version`, `wire_format`, and `notes` top-level sections
- [x] 2.2 Define `types` section: `Character`, `Event`, `EventFlags`, `EventContext` with all fields, types, required flags, enums, and descriptions matching both Lua and Python codebases
- [x] 2.3 Define Lua→Python messages: `game.event`, `player.dialogue`, `player.whisper`, `config.update`, `config.sync`, `system.heartbeat` with direction, description, and payload schemas
- [x] 2.4 Define Python→Lua commands: `dialogue.display`, `memory.update`, `event.store`, `config.request`, `service.heartbeat.ack` with direction, description, and payload schemas
- [x] 2.5 Define state query messages: `state.query.memories`, `state.query.events`, `state.query.character`, `state.query.characters_nearby`, `state.query.characters_alive`, `state.query.world` with direction, description, request, and response schemas
- [x] 2.6 Define `state.response` envelope message with `request_id`, `response_type`, `data`, `error` fields
- [x] 2.7 Verify all fields in the YAML match actual Lua serialization (`publisher.lua`, `talker_zmq_query_handlers.script`) and Python models (`messages.py`, `state/models.py`, `state/client.py`)

## 3. Schema Compiler

- [x] 3.1 Create `talker_service/tests/e2e/schema_compiler.py` with `compile_schema(yaml_path) -> dict` function
- [x] 3.2 Implement YAML loading and `types:` → JSON Schema `$defs` translation
- [x] 3.3 Implement field attribute mapping: `type`, `required`, `default`, `enum`, `$ref`, `items` → JSON Schema equivalents
- [x] 3.4 Implement `messages:` → per-topic JSON Schema dicts for `payload`, `request`, `response`
- [x] 3.5 Ensure all compiled schemas set `additionalProperties: true` (tolerant of extra fields)

## 4. E2E Scenario Validation

- [x] 4.1 Add schema validation hook to `talker_service/tests/e2e/conftest.py` that runs during test collection
- [x] 4.2 Validate `input.payload` against the compiled schema for `input.topic`
- [x] 4.3 Validate each `state_mocks.<topic>.response` against the response schema for that topic
- [x] 4.4 Validate each `expected.zmq_published[].payload` against the payload schema for that entry's topic
- [x] 4.5 Validate each `expected.state_queries[].payload` against the request schema for that entry's topic
- [x] 4.6 Verify existing `death_wolf_full.json` scenario passes schema validation

## 5. Cleanup

- [x] 5.1 Delete `docs/ZMQ_Message_Schema.md`
- [x] 5.2 Update any references to `ZMQ_Message_Schema.md` in `AGENTS.md`, `README.md`, or other docs to point to `docs/zmq-api.yaml`
- [x] 5.3 Run full test suite to verify no regressions
