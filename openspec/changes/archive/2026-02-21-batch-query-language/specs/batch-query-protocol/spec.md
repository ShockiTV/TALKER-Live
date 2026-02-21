# batch-query-protocol

## Purpose

Wire protocol for the `state.query.batch` ZMQ endpoint — request/response schema, per-query error isolation, `$ref` cross-query references, and `store.*`/`query.*` resource naming convention.

## Requirements

### Requirement: Batch request message format

The system SHALL accept batch queries on ZMQ topic `state.query.batch`. The request payload SHALL contain:
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

The response SHALL be published on ZMQ topic `state.response` with:
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
- `store.*` — In-memory Lua data stores. Filter engine SHALL apply when filter is present.
- `query.*` — Game engine pass-through queries. Params-driven. Filter engine SHALL apply as post-filter when result is an array.

#### Scenario: store.events is filterable
- **WHEN** sub-query has `resource: "store.events"` and a `filter` document
- **THEN** the filter engine SHALL be applied to the event collection

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

### Requirement: Resource registry

The system SHALL support the following resources:

| Resource | Source | Returns |
|----------|--------|---------|
| `store.events` | event_store:get_all_events() | Array of Event objects |
| `store.memories` | memory_store:get_memory_context(character_id) | Single MemoryContext object |
| `store.personalities` | personalities repo (character_personalities map) | Array of {character_id, personality_id} objects |
| `store.backstories` | backstories repo (character_backstories map) | Array of {character_id, backstory_id} objects |
| `store.levels` | levels repo (visits map) | Array of {level_id, count, log[]} objects |
| `store.timers` | timers repo | Single object {game_time_accumulator, idle_last_check_time} |
| `query.character` | game_adapter.get_character_by_id(id) | Single Character object |
| `query.characters_nearby` | game_adapter.get_characters_near(center, radius) | Array of Character objects |
| `query.characters_alive` | alife() story object checks | Object mapping story_id to boolean |
| `query.world` | talker_game_queries (location, time, weather, etc.) | Single SceneContext object |

#### Scenario: store.events returns event collection
- **WHEN** sub-query is `{"id": "ev", "resource": "store.events"}`
- **THEN** result data SHALL be an array of serialized Event objects

#### Scenario: store.memories returns memory context for character
- **WHEN** sub-query is `{"id": "mem", "resource": "store.memories", "params": {"character_id": "123"}}`
- **THEN** result data SHALL contain `narrative`, `last_update_time_ms`, and `new_events`

#### Scenario: store.memories requires character_id
- **WHEN** sub-query is `{"id": "mem", "resource": "store.memories"}` with no params
- **THEN** result SHALL have `ok: false` with error about missing character_id

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
- **WHEN** queries are `[{"id": "mem", "resource": "store.memories", ...}, {"id": "ev", "resource": "store.events", "filter": {"game_time_ms": {"$gt": "$ref:mem.last_update_time_ms"}}}]`
- **AND** "mem" result has `data.last_update_time_ms = 50000`
- **THEN** "ev" filter SHALL be resolved to `{"game_time_ms": {"$gt": 50000}}`

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

### Requirement: Filter, sort, limit, and projection pipeline

For collection resources, the query pipeline SHALL use the filter engine's `execute_pipeline` orchestrator which selects a memory-efficient strategy based on which stages are present. Projection SHALL apply last, only to the final bounded result set.

The logical order of operations remains: filter → sort → limit → project. The orchestrator MAY fuse stages (e.g., fused top-N scan when both sort and limit are present) to minimize intermediate memory, but the result SHALL be identical to the sequential pipeline.

Collection resources SHALL provide an **iterator function** to the pipeline rather than a pre-materialized array. For `store.events`, the iterator SHOULD start from a binary-search position on `sorted_keys` when the filter contains a `game_time_ms` range condition (`$gt`, `$gte`), skipping events before the threshold.

#### Scenario: Full pipeline on store.events
- **WHEN** sub-query has filter, sort, limit, and fields
- **THEN** the pipeline SHALL produce the same results as filter → sort → limit → project
- **AND** peak memory during the scan SHALL be O(limit) document references (fused top-N)
- **AND** projection and serialization SHALL apply only to the final limited set

#### Scenario: Limit without sort
- **WHEN** sub-query has limit but no sort
- **THEN** the pipeline SHALL stop scanning after `limit` matches (early termination)

#### Scenario: Time-range filter uses index pre-scan
- **WHEN** sub-query targets `store.events` with filter `{"game_time_ms": {"$gt": 50000}}`
- **THEN** the events iterator SHALL start from the binary-search position for 50000 in `sorted_keys`
- **AND** events before that position SHALL NOT be visited

#### Scenario: Projection on document resource
- **WHEN** sub-query for `query.character` includes `fields: ["name", "faction"]`
- **THEN** result data SHALL contain only `name` and `faction` fields
