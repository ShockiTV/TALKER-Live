## Why

The ZMQ API contract between Lua and Python exists in three drifting representations: Lua serialization code (`publisher.lua`, `query_handlers.script`, `command_handlers.script`), Python Pydantic/dataclass models (`messages.py`, `state/models.py`), and a prose markdown document (`docs/ZMQ_Message_Schema.md`). The markdown doc is already stale — it's missing `state.query.world`, `state.query.characters_alive`, `config.request`, `service.heartbeat.ack`, and `event.store` topics. There is no machine-readable contract and no automated validation that scenario files conform to the actual schema.

## What Changes

- Create `docs/zmq-api.yaml` as the single source of truth for the ZMQ API contract — all topics, directions, payload structures, shared types, and state query request/response pairs
- Create a thin schema compiler (`tests/e2e/schema_compiler.py`) that translates the human-friendly YAML into JSON Schema dicts at validation time
- Add a pytest fixture/hook in the e2e test suite that validates each scenario file's payloads against the compiled schema
- Remove `docs/ZMQ_Message_Schema.md` (replaced by `docs/zmq-api.yaml`)

## Capabilities

### New Capabilities
- `zmq-api-contract`: The YAML schema file defining all ZMQ topics, directions, payload structures, shared types, and state query request/response pairs — the single source of truth for the Lua↔Python wire protocol
- `zmq-schema-validation`: Schema compiler that translates the YAML to JSON Schema, plus e2e pytest integration that validates scenario files against it

### Modified Capabilities
- `e2e-test-harness`: Scenario files are now validated against the compiled ZMQ schema at test collection time

## Impact

- **Docs**: `docs/ZMQ_Message_Schema.md` removed, replaced by `docs/zmq-api.yaml`
- **Python tests**: New `jsonschema` dependency (dev). New validation step in e2e conftest.
- **E2e scenarios**: Existing `death_wolf_full.json` (and future scenarios) must conform to the schema — payloads validated automatically
- **No runtime code changes**: Neither Lua nor Python runtime code is modified — this is purely a documentation and test-infrastructure change
