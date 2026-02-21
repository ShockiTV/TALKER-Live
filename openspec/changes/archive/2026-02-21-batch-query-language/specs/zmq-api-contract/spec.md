# zmq-api-contract

## ADDED Requirements

### Requirement: state.query.batch message definition

The `messages` section SHALL define the `state.query.batch` topic with `direction: python→lua→python`.

The `request` payload SHALL define:
- `request_id` (string, required): Unique correlation ID
- `queries` (array, required): Ordered array of sub-query objects

Each sub-query SHALL define:
- `id` (string, required): Unique identifier within the batch
- `resource` (string, required): Resource name in `store.*` or `query.*` format
- `params` (object, optional): Resource-specific parameters
- `filter` (object, optional): MongoDB-style filter document
- `sort` (object, optional): Sort specification
- `limit` (integer, optional): Maximum results
- `fields` (array of string, optional): Field projection paths

The `response` payload SHALL define:
- `request_id` (string, required): Correlated to the request
- `results` (object, required): Map of sub-query ID to result object containing `ok` (bool) and either `data` or `error` (string)

#### Scenario: state.query.batch is fully defined
- **WHEN** the `state.query.batch` message is read from the schema
- **THEN** its `direction` SHALL be `python→lua→python`
- **AND** its `request` SHALL define `request_id` and `queries` array with sub-query schema
- **AND** its `response` SHALL define `request_id` and `results` map

### Requirement: Filter document type definition

The `types` section SHALL define a `FilterDocument` type documenting all supported operators:
- Comparison: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`
- Set: `$in`, `$nin`
- String: `$regex`, `$regex_flags`
- Existence: `$exists`
- Array: `$elemMatch`, `$size`, `$all`
- Logical: `$and`, `$or`, `$not`
- Reference: `$ref:<id>.<path>` string syntax

#### Scenario: FilterDocument type is defined in schema
- **WHEN** the `FilterDocument` type is read from `docs/zmq-api.yaml`
- **THEN** it SHALL list all supported operators with descriptions and value types

### Requirement: Resource registry documentation

The schema SHALL document the available resources and their parameters in a `resources` section or as part of the `state.query.batch` message definition.

#### Scenario: All resources documented
- **WHEN** a developer reads the `state.query.batch` definition
- **THEN** they SHALL find documentation for `store.events`, `store.memories`, `store.personalities`, `store.backstories`, `store.levels`, `store.timers`, `query.character`, `query.characters_nearby`, `query.characters_alive`, and `query.world`
- **AND** each resource SHALL list its required and optional `params`

## REMOVED Requirements

### Requirement: State query definitions

**Reason**: Individual `state.query.*` topics replaced by single `state.query.batch` endpoint
**Migration**: All state queries use `state.query.batch` with appropriate `resource` name:
- `state.query.memories` → `{"resource": "store.memories", "params": {"character_id": "..."}}`
- `state.query.events` → `{"resource": "store.events"}` with optional filter/sort/limit
- `state.query.character` → `{"resource": "query.character", "params": {"id": "..."}}`
- `state.query.characters_nearby` → `{"resource": "query.characters_nearby", "params": {"radius": 50}}`
- `state.query.characters_alive` → `{"resource": "query.characters_alive", "params": {"ids": [...]}}`
- `state.query.world` → `{"resource": "query.world"}`
