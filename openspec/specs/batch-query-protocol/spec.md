# batch-query-protocol

## Purpose

Wire protocol for the `state.query.batch` and `state.mutate.batch` WS endpoints — request/response schema, per-query error isolation, `$ref` cross-query references, and `memory.*`/`store.*`/`query.*` resource naming convention.

## Requirements

### Requirement: Batch request message format

The system SHALL accept batch queries on WS topic `state.query.batch`. The request payload SHALL contain:
- `request_id` (string, required): Unique correlation ID
- `queries` (array, required): Ordered array of sub-query objects

Each sub-query object SHALL contain:
- `id` (string, required): Unique identifier within the batch, used to key the response
- `resource` (string, required): Resource name in `<type>.<name>` format
- `params` (object, optional): Resource-specific parameters
- `filter` (object, optional): MongoDB-style filter document (for collection resources)
- `sort` (object, optional): Sort specification `{"field": 1}` or `{"field": -1}`
- `limit` (integer, optional): Maximum number of results
- `fields` (array of string, optional): Field projection paths

#### Scenario: Valid batch request accepted
- **WHEN** Python publishes `state.query.batch` with `request_id` and `queries` array
- **THEN** Lua SHALL process all sub-queries and return results

#### Scenario: Empty queries array
- **WHEN** batch request has `queries: []`
- **THEN** response SHALL contain empty `results` object

### Requirement: Batch response message format

The response SHALL be published on WS topic `state.response` with:
- `request_id` (string): Correlated to the request
- `results` (object): Map of sub-query `id` to result object

Each result object SHALL contain either:
- `ok: true` and `data` (the query result — object or array depending on resource)
- `ok: false` and `error` (string describing the failure)

#### Scenario: Successful batch response
- **WHEN** all sub-queries succeed
- **THEN** each result SHALL have `ok: true` and `data` containing the resource result

#### Scenario: Partial failure response
- **WHEN** sub-query "char" succeeds but sub-query "mem" fails
- **THEN** `results.char` SHALL have `ok: true` with data
- **AND** `results.mem` SHALL have `ok: false` with error message
- **AND** other successful queries SHALL NOT be affected

#### Scenario: Per-query error isolation
- **WHEN** one sub-query throws an error during execution
- **THEN** only that sub-query's result SHALL have `ok: false`
- **AND** remaining queries SHALL continue executing

### Requirement: Resource naming convention

Resources SHALL use a `<type>.<name>` naming convention:
- `memory.*` — Per-NPC memory store tiers. Delegated to memory_store DSL. Requires `params.character_id`.
- `store.*` — In-memory Lua data stores. Filter engine SHALL apply when filter is present.
- `query.*` — Game engine pass-through queries. Params-driven. Filter engine SHALL apply as post-filter when result is an array.

#### Scenario: query.character is params-only
- **WHEN** sub-query has `resource: "query.character"` with `params: {"id": "123"}`
- **THEN** the character SHALL be looked up by ID without filter engine involvement

#### Scenario: query.characters_nearby supports post-filter
- **WHEN** sub-query has `resource: "query.characters_nearby"` with params and a `filter`
- **THEN** the spatial query SHALL execute first
- **AND** the filter engine SHALL be applied to the returned array as a post-filter

#### Scenario: Unknown resource returns error
- **WHEN** sub-query has `resource: "store.nonexistent"`
- **THEN** result SHALL have `ok: false` and error `"unknown resource: store.nonexistent"`

### Requirement: Memory query resources

The resource registry SHALL support the following memory-specific resources for `state.query.batch`:

| Resource | Returns |
|----------|---------|
| `memory.events` | Array of structured event objects for a character |
| `memory.summaries` | Array of compressed memory objects for a character |
| `memory.digests` | Array of compressed memory objects for a character |
| `memory.cores` | Array of compressed memory objects for a character |
| `memory.background` | Single Background object (or null) for a character |

All memory resources require `params.character_id`.

#### Scenario: memory.events returns character events
- **WHEN** sub-query is `{"id": "ev", "resource": "memory.events", "params": {"character_id": "12467"}}`
- **THEN** result data SHALL be an array of structured event objects from character 12467's memory

#### Scenario: memory.events with from_timestamp filter
- **WHEN** sub-query includes `"params": {"character_id": "12467", "from_timestamp": 340}`
- **THEN** only events with `timestamp >= 340` SHALL be returned

#### Scenario: memory.background returns null for new character
- **WHEN** sub-query queries `memory.background` for a character with no background
- **THEN** result data SHALL be `null`

#### Scenario: memory.summaries returns compressed memories
- **WHEN** sub-query queries `memory.summaries` for a character
- **THEN** result data SHALL be an array of `{seq, tier, start_ts, end_ts, text, source_count}` objects

#### Scenario: memory resource requires character_id
- **WHEN** sub-query queries `memory.events` without `params.character_id`
- **THEN** result SHALL have `ok: false` with error about missing character_id

### Requirement: Mutation handler topic

The system SHALL register a handler for WS topic `state.mutate.batch` that dispatches mutation operations to the memory store DSL. The handler SHALL follow the same error isolation pattern as `state.query.batch`.

#### Scenario: Mutation handler registered
- **WHEN** `state.mutate.batch` message is received with `mutations` array
- **THEN** each mutation SHALL be dispatched to the memory_store DSL
- **AND** results SHALL be collected into a `state.response` message

#### Scenario: Unknown resource in mutation
- **WHEN** mutation targets an unrecognized resource
- **THEN** that mutation's result SHALL have `ok: false`
- **AND** other mutations SHALL still execute

### Requirement: Resource registry

The system SHALL support the following resources:

| Resource | Source | Returns |
|----------|--------|---------|
| `memory.events` | memory_store:query(char_id, "memory.events", params) | Array of structured event objects |
| `memory.summaries` | memory_store:query(char_id, "memory.summaries", params) | Array of CompressedMemory objects |
| `memory.digests` | memory_store:query(char_id, "memory.digests", params) | Array of CompressedMemory objects |
| `memory.cores` | memory_store:query(char_id, "memory.cores", params) | Array of CompressedMemory objects |
| `memory.background` | memory_store:query(char_id, "memory.background", params) | Single Background object or null |
| `store.personalities` | personalities repo (character_personalities map) | Array of {character_id, personality_id} objects |
| `store.backstories` | backstories repo (character_backstories map) | Array of {character_id, backstory_id} objects |
| `store.levels` | levels repo (visits map) | Array of {level_id, count, log[]} objects |
| `store.timers` | timers repo | Single object {game_time_accumulator, idle_last_check_time} |
| `query.character` | game_adapter.get_character_by_id(id) | Single Character object |
| `query.characters_nearby` | game_adapter.get_characters_near(center, radius) | Array of Character objects |
| `query.characters_alive` | alife() story object checks | Object mapping story_id to boolean |
| `query.world` | talker_game_queries (location, time, weather, etc.) | Single SceneContext object |

#### Scenario: store.events is removed from registry
- **WHEN** sub-query has `resource: "store.events"`
- **THEN** result SHALL have `ok: false` with error `"unknown resource: store.events"`

#### Scenario: store.memories is removed from registry
- **WHEN** sub-query has `resource: "store.memories"`
- **THEN** result SHALL have `ok: false` with error `"unknown resource: store.memories"`

#### Scenario: memory.events returns structured events
- **WHEN** sub-query is `{"id": "ev", "resource": "memory.events", "params": {"character_id": "12467"}}`
- **THEN** result data SHALL be an array of `{seq, timestamp, type, context}` objects

#### Scenario: query.character returns character data
- **WHEN** sub-query is `{"id": "c", "resource": "query.character", "params": {"id": "123"}}`
- **THEN** result data SHALL contain serialized Character fields (game_id, name, faction, etc.)

#### Scenario: query.world returns scene context
- **WHEN** sub-query is `{"id": "w", "resource": "query.world"}`
- **THEN** result data SHALL contain loc, poi, time, weather, emission, psy_storm, sheltering, campfire, brain_scorcher_disabled, miracle_machine_disabled

#### Scenario: store.personalities returns character-to-personality mappings
- **WHEN** sub-query is `{"id": "p", "resource": "store.personalities"}`
- **THEN** result data SHALL be an array of `{character_id, personality_id}` objects
- **AND** filter engine SHALL apply (e.g., filter by personality_id pattern)

#### Scenario: store.backstories returns character-to-backstory mappings
- **WHEN** sub-query is `{"id": "b", "resource": "store.backstories"}`
- **THEN** result data SHALL be an array of `{character_id, backstory_id}` objects
- **AND** filter engine SHALL apply

#### Scenario: store.levels returns visit history
- **WHEN** sub-query is `{"id": "lv", "resource": "store.levels"}`
- **THEN** result data SHALL be an array of `{level_id, count, log}` objects per visited level
- **AND** filter engine SHALL apply (e.g., filter by count or level_id)

#### Scenario: store.levels with level_id param returns single level
- **WHEN** sub-query is `{"id": "lv", "resource": "store.levels", "params": {"level_id": "l01_escape"}}`
- **THEN** result data SHALL be a single `{level_id, count, log}` object for that level

#### Scenario: store.timers returns timer singleton
- **WHEN** sub-query is `{"id": "t", "resource": "store.timers"}`
- **THEN** result data SHALL contain `game_time_accumulator` and `idle_last_check_time`

### Requirement: Sequential execution with $ref resolution

Sub-queries SHALL execute in array order. String values in `filter` or `params` starting with `"$ref:"` SHALL be resolved against results of earlier (already-completed) sub-queries before execution.

The `$ref` syntax SHALL be: `"$ref:<query_id>.<dotted.path>"`

Resolution SHALL traverse the `data` field of the referenced query's result using dotted path resolution (identical to the filter engine's field resolver).

#### Scenario: $ref resolves value from earlier query
- **WHEN** queries are `[{"id": "mem", "resource": "memory.events", ...}, {"id": "ev", "resource": "memory.summaries", "filter": {"start_ts": {"$gt": "$ref:mem.0.timestamp"}}}]`
- **AND** "mem" result has `data[0].timestamp = 50000`
- **THEN** "ev" filter SHALL be resolved to `{"start_ts": {"$gt": 50000}}`

#### Scenario: $ref to unresolved query returns error
- **WHEN** sub-query references `"$ref:foo.bar"` and no query with `id: "foo"` has executed yet
- **THEN** the referencing sub-query SHALL have `ok: false` with error `"$ref: 'foo' not yet resolved"`

#### Scenario: $ref to failed query cascades error
- **WHEN** query "mem" failed with `ok: false`
- **AND** query "ev" references `"$ref:mem.last_update_time_ms"`
- **THEN** query "ev" SHALL have `ok: false` with error `"$ref: 'mem' resolved to error"`

#### Scenario: $ref resolves in params
- **WHEN** sub-query has `params: {"character_id": "$ref:char.game_id"}`
- **AND** query "char" has `data.game_id = "12345"`
- **THEN** params SHALL resolve to `{"character_id": "12345"}`

#### Scenario: $ref resolves deeply nested in filter
- **WHEN** `$ref` string appears inside a `$elemMatch` or `$and` within the filter
- **THEN** the recursive $ref resolver SHALL find and replace it regardless of nesting depth
