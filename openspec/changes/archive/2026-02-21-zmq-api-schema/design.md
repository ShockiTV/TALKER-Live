## Context

The ZMQ API between Lua and Python currently has no machine-readable contract. The wire protocol is defined implicitly by three drifting sources: Lua serialization code (`publisher.lua`, `talker_zmq_query_handlers.script`, `talker_zmq_command_handlers.script`), Python models (`messages.py`, `state/models.py`, `state/client.py`), and a prose markdown file (`docs/ZMQ_Message_Schema.md`). The markdown is already stale — missing several topics added since it was written.

The e2e test harness validates actual wire payloads via JSON scenario files, but there is no schema enforcement on the scenario files themselves. A scenario file could contain malformed payloads and the only feedback would come at runtime.

## Goals / Non-Goals

**Goals:**
- Single source of truth for the ZMQ API contract in a human-readable, machine-parseable format
- Automated validation of e2e scenario file payloads against the schema at test collection time
- Complete coverage of all current topics (including ones missing from the stale markdown)

**Non-Goals:**
- Runtime schema validation in Lua or Python application code — this is test-time only
- Code generation from the schema (Pydantic models, Lua serializers) — future opportunity, not in scope
- Changing any Lua or Python runtime behavior — purely documentation + test infrastructure

## Decisions

### 1. Custom YAML format with thin JSON Schema compiler

**Decision**: Use a human-friendly YAML schema format (`docs/zmq-api.yaml`) and a ~50-line Python module that translates it to standard JSON Schema dicts at validation time.

**Alternatives considered**:
- **Pure JSON Schema as YAML**: Too verbose for humans. JSON Schema ceremony (`$defs`, `additionalProperties: false`, `oneOf`, etc.) makes the file hard to scan and edit casually.
- **Pure custom validator**: Full control but reinvents type checking. Fragile long-term — every edge case needs a custom code path.
- **Pydantic-as-source**: Python already has rich types, but Lua side has nuances not captured in Pydantic (e.g., `visual_faction` present in Lua serialization but missing from Python's `CharacterData`). Lossy one-directional sync.

**Rationale**: The hybrid approach keeps the YAML pleasant to read (it's a reference doc first, machine-readable schema second) while leveraging the battle-tested `jsonschema` library for actual validation.

### 2. Schema file location: `docs/zmq-api.yaml`

**Decision**: Place the schema in `docs/` alongside other documentation.

**Rationale**: It replaces `docs/ZMQ_Message_Schema.md` directly. The `docs/` directory is the natural home for cross-cutting documentation. Both Lua and Python developers look there.

### 3. Compiler location: `talker_service/tests/e2e/schema_compiler.py`

**Decision**: Place the compiler in the e2e test directory since it's only used at test time.

**Rationale**: No production dependency on the compiler. If future use cases emerge (CI docs generation, etc.), it can be extracted to a shared util.

### 4. Validation timing: pytest collection phase

**Decision**: Validate scenario payloads during pytest collection (via `conftest.py` hook or a parametrize wrapper), not at test runtime.

**Rationale**: Schema violations should fail fast — before any ZMQ sockets spin up. A scenario with a malformed payload should be a collection error, not a mysterious runtime failure.

### 5. YAML schema format conventions

**Decision**: The custom YAML format uses these conventions:
- `types:` section defines reusable data structures (Character, Event, EventFlags, etc.)
- `messages:` section defines each topic with `direction`, `description`, `payload` (or `request`/`response` for state queries)
- Field attributes: `type`, `required` (default false), `default`, `description`, `enum`, `items` (for arrays), `$ref` (for type references)
- Types support `string`, `int`, `float`, `bool`, `object`, `array`, and `any`
- The `state.response` meta-topic wraps all query responses with `request_id` + `data`

**Rationale**: Minimal syntax that maps cleanly to JSON Schema concepts. The compiler translates mechanically: `required: true` → JSON Schema `required` array, `$ref: TypeName` → `$ref: "#/$defs/TypeName"`, `enum: [a, b]` → `enum: ["a", "b"]`, etc.

## Risks / Trade-offs

**[Schema drift from runtime code]** → The schema is still manually maintained. Mitigation: e2e scenarios act as integration tests — if runtime code changes payload shapes, scenarios fail, signaling the schema needs updating. This closes the loop for the Python side. Lua drift is only caught if a scenario exercises that topic.

**[Compiler maintenance burden]** → The translation layer is custom code. Mitigation: It's intentionally thin (~50 lines). The mapping from custom YAML to JSON Schema is mechanical and well-defined. If it becomes painful, the YAML can be replaced with native JSON Schema.

**[Partial coverage]** → Only topics exercised by e2e scenarios get validated. Mitigation: Schema validation also runs as a standalone test (compile + validate every scenario vs. every relevant topic). Future scenarios expand coverage organically.

**[Lua empty table ambiguity]** → Lua serializes `{}` as either JSON `{}` or `[]`. Mitigation: Schema uses `type: object` with a note about empty-table handling. Validation allows both forms where documented.
