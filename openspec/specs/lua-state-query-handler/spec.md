# lua-state-query-handler

## Purpose

Lua batch query handler that responds to `state.query.batch` requests, dispatching sub-queries to a resource registry and returning all results in a single response.

## Requirements

### Requirement: Batch query dispatcher

The system SHALL register a handler for WS topic `state.query.batch` that accepts an array of sub-queries and dispatches each to the appropriate resource resolver based on resource prefix:
- `memory.*` → memory_store query DSL
- `store.*` → data store repos
- `query.*` → game adapter / game queries

Results SHALL be collected into a single response keyed by sub-query `id`.

#### Scenario: Batch dispatches to resource resolvers
- **WHEN** `state.query.batch` is received with 3 sub-queries for different resources
- **THEN** each sub-query SHALL be dispatched to its registered resource resolver
- **AND** all results SHALL be returned in a single `state.response` message

#### Scenario: Batch applies filter engine to store resources
- **WHEN** a sub-query targets a `store.*` resource with a `filter` document
- **THEN** the filter engine from `bin/lua/infra/query/filter_engine.lua` SHALL be applied to the collection

#### Scenario: Batch applies sort, limit, and projection pipeline
- **WHEN** a sub-query includes `filter`, `sort`, `limit`, and `fields`
- **THEN** the pipeline SHALL execute in order: filter → sort → limit → project

### Requirement: Memory resource resolvers

The state query handler SHALL resolve memory-specific resources by delegating to the memory_store's query DSL:

| Resource | Resolver |
|----------|----------|
| `memory.events` | `memory_store:query(character_id, "memory.events", params)` |
| `memory.summaries` | `memory_store:query(character_id, "memory.summaries", params)` |
| `memory.digests` | `memory_store:query(character_id, "memory.digests", params)` |
| `memory.cores` | `memory_store:query(character_id, "memory.cores", params)` |
| `memory.background` | `memory_store:query(character_id, "memory.background", params)` |

#### Scenario: Resolve memory.events query
- **WHEN** a `state.query.batch` sub-query has `resource: "memory.events"` with `params.character_id: "12467"`
- **THEN** the handler SHALL call `memory_store:query("12467", "memory.events", params)`
- **AND** return the result as the sub-query data

#### Scenario: Memory resource with missing character_id
- **WHEN** a memory resource sub-query omits `params.character_id`
- **THEN** the sub-query result SHALL have `ok: false` with error message

### Requirement: State mutation handler

The state query handler module SHALL register a handler for the `state.mutate.batch` WS topic. The handler SHALL:
1. Parse the `mutations` array from the payload
2. For each mutation, dispatch to `memory_store:mutate(character_id, verb, resource, data)`
3. Collect results into a response array
4. Send `state.response` with the request's correlation ID

#### Scenario: Handle append mutation
- **WHEN** `state.mutate.batch` payload contains `{mutations: [{verb: "append", resource: "memory.summaries", params: {character_id: "123"}, data: {text: "..."}}]}`
- **THEN** the handler SHALL call `memory_store:mutate("123", "append", "memory.summaries", data)`
- **AND** respond with `state.response` containing `{results: [{ok: true}]}`

#### Scenario: Handle delete mutation
- **WHEN** mutation has `{verb: "delete", resource: "memory.events", params: {character_id: "123"}, data: {seq_lte: 50}}`
- **THEN** the handler SHALL delete all events with `seq <= 50` from character 123's events tier

#### Scenario: Mixed success and failure mutations
- **WHEN** a batch contains 3 mutations and the 2nd targets an unknown resource
- **THEN** mutations 1 and 3 SHALL succeed
- **AND** mutation 2 SHALL return `{ok: false, error: "unknown resource"}`

### Requirement: Resource registry

The batch handler SHALL maintain a static resource registry mapping resource names to resolver functions. Adding a new resource SHALL require only adding an entry to this registry.

The resource registry SHALL include all memory resources (`memory.events`, `memory.summaries`, `memory.digests`, `memory.cores`, `memory.background`) alongside existing resources (`store.personalities`, `store.backstories`, `store.levels`, `store.timers`, `query.character`, `query.characters_nearby`, `query.characters_alive`, `query.world`).

Serialization of resolved data SHALL use `infra.ws.serializer` module functions instead of inline serialization.

#### Scenario: Registry includes memory resources
- **GIVEN** the resource registry
- **THEN** it SHALL contain entries for `memory.events`, `memory.summaries`, `memory.digests`, `memory.cores`, `memory.background`

#### Scenario: store.events no longer in registry
- **WHEN** resolving resource `store.events`
- **THEN** result SHALL be `{ok: false, error: "unknown resource: store.events"}`

#### Scenario: Resource registry maps store.personalities
- **WHEN** sub-query has `resource: "store.personalities"`
- **THEN** registry SHALL map it to the personalities repo character_personalities map, serialized as `{character_id, personality_id}` collection

#### Scenario: Resource registry maps query.character
- **WHEN** sub-query has `resource: "query.character"` with a `params.character_id`
- **THEN** the resolver SHALL serialize the character using `serializer.serialize_character()`

#### Scenario: Resource registry maps store.backstories
- **WHEN** sub-query has `resource: "store.backstories"`
- **THEN** registry SHALL map it to the backstories repo character_backstories map, serialized as `{character_id, backstory_id}` collection

#### Scenario: Resource registry maps store.levels
- **WHEN** sub-query has `resource: "store.levels"`
- **THEN** registry SHALL map it to the levels repo visits map, serialized as `{level_id, count, log}` collection

#### Scenario: Resource registry maps store.timers
- **WHEN** sub-query has `resource: "store.timers"`
- **THEN** registry SHALL map it to the timers repo, returning singleton `{game_time_accumulator, idle_last_check_time}`

#### Scenario: Resource registry maps query.world
- **WHEN** sub-query has `resource: "query.world"`
- **THEN** registry SHALL map it to the world context builder (location, time, weather, etc.)

#### Scenario: Unknown resource returns per-query error
- **WHEN** sub-query has an unrecognized resource name
- **THEN** the result for that sub-query SHALL have `ok: false` with a descriptive error

### Requirement: $ref cross-query reference resolution

The batch handler SHALL resolve `$ref` strings in sub-query `filter` and `params` fields against results from previously executed sub-queries in the same batch. Queries SHALL execute in array order. `$ref` resolution applies to both query and mutation result payloads.

#### Scenario: $ref resolves from earlier query result
- **WHEN** sub-query "ev" has filter with `"$ref:mem.last_update_time_ms"`
- **AND** sub-query "mem" executed earlier with `data.last_update_time_ms = 50000`
- **THEN** the `$ref` string SHALL be replaced with `50000` before filter evaluation

#### Scenario: $ref to failed query cascades error
- **WHEN** referenced query "mem" has `ok: false`
- **THEN** the referencing sub-query SHALL have `ok: false` with error `"$ref: 'mem' resolved to error"`

### Requirement: Dialogue Display Command Handler

The system MUST handle `dialogue.display {speaker_id, speaker_name, text}` commands.

#### Scenario: Display dialogue command
- **WHEN** Python sends dialogue.display command
- **THEN** game displays the dialogue via HUD
- **AND** dialogue event is created and stored


