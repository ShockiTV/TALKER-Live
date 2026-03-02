## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Resource registry

The resource registry SHALL include all memory resources (`memory.events`, `memory.summaries`, `memory.digests`, `memory.cores`, `memory.background`) alongside existing resources (`store.personalities`, `store.backstories`, `store.levels`, `store.timers`, `query.character`, `query.characters_nearby`, `query.characters_alive`, `query.world`).

#### Scenario: Registry includes memory resources
- **GIVEN** the resource registry
- **THEN** it SHALL contain entries for `memory.events`, `memory.summaries`, `memory.digests`, `memory.cores`, `memory.background`

#### Scenario: store.events no longer in registry
- **WHEN** resolving resource `store.events`
- **THEN** result SHALL be `{ok: false, error: "unknown resource: store.events"}`

### Requirement: Batch query dispatcher

The batch query dispatcher SHALL dispatch sub-queries to the appropriate resolver based on resource prefix:
- `memory.*` → memory_store query DSL
- `store.*` → data store repos
- `query.*` → game adapter / game queries

### Requirement: $ref resolution

`$ref` resolution SHALL remain unchanged — it applies to both query and mutation result payloads.

## REMOVED Requirements

### Requirement: Memory Update Command Handler
**Reason**: The old `memory.update` command handler that replaced the entire narrative blob is obsolete. Memory mutations now use `state.mutate.batch` with fine-grained operations (append/delete/set/update).
**Migration**: Replace the `memory.update` command handler with the `state.mutate.batch` handler.

### Requirement: store.events resource resolver
**Reason**: The global event_store is eliminated. Events are stored per-NPC via `memory.events`.
**Migration**: Use `memory.events` resource with `character_id` param instead.

### Requirement: store.memories resource resolver
**Reason**: The flat narrative memory blob is replaced by structured 4-tier memory. Use `memory.summaries`, `memory.digests`, `memory.cores`, `memory.background` resources.
**Migration**: Python queries the specific tier it needs.
