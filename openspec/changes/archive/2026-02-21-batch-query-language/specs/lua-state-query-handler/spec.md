# lua-state-query-handler

## ADDED Requirements

### Requirement: Batch query dispatcher

The system SHALL register a handler for ZMQ topic `state.query.batch` that accepts an array of sub-queries and dispatches each to the appropriate resource resolver. Results SHALL be collected into a single response keyed by sub-query `id`.

#### Scenario: Batch dispatches to resource resolvers
- **WHEN** `state.query.batch` is received with 3 sub-queries for different resources
- **THEN** each sub-query SHALL be dispatched to its registered resource resolver
- **AND** all results SHALL be returned in a single `state.response` message

#### Scenario: Batch applies filter engine to store resources
- **WHEN** a sub-query targets `store.events` with a `filter` document
- **THEN** the filter engine from `bin/lua/infra/query/filter_engine.lua` SHALL be applied to the event collection

#### Scenario: Batch applies sort, limit, and projection pipeline
- **WHEN** a sub-query includes `filter`, `sort`, `limit`, and `fields`
- **THEN** the pipeline SHALL execute in order: filter → sort → limit → project

### Requirement: Resource registry

The batch handler SHALL maintain a static resource registry mapping resource names to resolver functions. Adding a new resource SHALL require only adding an entry to this registry.

#### Scenario: Resource registry maps store.events
- **WHEN** sub-query has `resource: "store.events"`
- **THEN** registry SHALL map it to `event_store:get_all_events()` as the collection source

#### Scenario: Resource registry maps store.personalities
- **WHEN** sub-query has `resource: "store.personalities"`
- **THEN** registry SHALL map it to the personalities repo character_personalities map, serialized as `{character_id, personality_id}` collection

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

The batch handler SHALL resolve `$ref` strings in sub-query `filter` and `params` fields against results from previously executed sub-queries in the same batch. Queries SHALL execute in array order.

#### Scenario: $ref resolves from earlier query result
- **WHEN** sub-query "ev" has filter with `"$ref:mem.last_update_time_ms"`
- **AND** sub-query "mem" executed earlier with `data.last_update_time_ms = 50000`
- **THEN** the `$ref` string SHALL be replaced with `50000` before filter evaluation

#### Scenario: $ref to failed query cascades error
- **WHEN** referenced query "mem" has `ok: false`
- **THEN** the referencing sub-query SHALL have `ok: false` with error `"$ref: 'mem' resolved to error"`

## REMOVED Requirements

### Requirement: Memories Query Handler

**Reason**: Replaced by batch dispatcher with `store.memories` resource
**Migration**: Use `state.query.batch` with `{"resource": "store.memories", "params": {"character_id": "..."}}`

### Requirement: Events Query Handler

**Reason**: Replaced by batch dispatcher with `store.events` resource
**Migration**: Use `state.query.batch` with `{"resource": "store.events"}` and optional filter/sort/limit

### Requirement: Character Query Handler

**Reason**: Replaced by batch dispatcher with `query.character` resource
**Migration**: Use `state.query.batch` with `{"resource": "query.character", "params": {"id": "..."}}`

### Requirement: Nearby Characters Query Handler

**Reason**: Replaced by batch dispatcher with `query.characters_nearby` resource
**Migration**: Use `state.query.batch` with `{"resource": "query.characters_nearby", "params": {"radius": 50}}`

### Requirement: Characters Alive Query Handler

**Reason**: Replaced by batch dispatcher with `query.characters_alive` resource
**Migration**: Use `state.query.batch` with `{"resource": "query.characters_alive", "params": {"ids": [...]}}`

### Requirement: World Context Query Handler

**Reason**: Replaced by batch dispatcher with `query.world` resource
**Migration**: Use `state.query.batch` with `{"resource": "query.world"}`
