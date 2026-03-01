# state-mutate-protocol

## Purpose

Wire protocol for the `state.mutate.batch` WS topic — batched write operations from Python to Lua memory store, supporting append, delete, set, and update verbs with ID-based addressing.

## Requirements

### Requirement: Batch mutation message format

The system SHALL accept batch mutations on WS topic `state.mutate.batch`. The request payload SHALL contain a `mutations` array of mutation objects. Each mutation object SHALL contain:
- `op` (string, required): One of `"append"`, `"delete"`, `"set"`, `"update"`
- `resource` (string, required): Resource name (e.g., `"memory.events"`, `"memory.background"`)
- `params` (object, required): Contains at minimum `character_id` (string)
- Verb-specific fields: `data` (for append/set), `ids` (for delete), `ops` (for update)

#### Scenario: Valid batch mutation accepted
- **WHEN** Python sends `state.mutate.batch` with `mutations` array
- **THEN** Lua SHALL process all mutations sequentially and return results

#### Scenario: Empty mutations array
- **WHEN** `mutations` is `[]`
- **THEN** response SHALL contain empty `results` object

### Requirement: Append verb

The `append` verb SHALL add items to a list-type resource. The `data` field SHALL contain an array of items to append.

#### Scenario: Append summaries after compaction
- **WHEN** mutation is `{"op": "append", "resource": "memory.summaries", "params": {"character_id": "12467"}, "data": [{"start_ts": 200, "end_ts": 380, "text": "...", "source_count": 10}]}`
- **THEN** the summary SHALL be appended to character 12467's summary tier with a new seq

#### Scenario: Append to non-existent character
- **WHEN** append targets a character with no memory entry
- **THEN** a new memory entry SHALL be created and the items appended

### Requirement: Delete verb

The `delete` verb SHALL remove items from a list-type resource by explicit ID (seq number). Non-existent IDs SHALL be silently skipped (idempotent).

#### Scenario: Delete events after compaction
- **WHEN** mutation is `{"op": "delete", "resource": "memory.events", "params": {"character_id": "12467"}, "ids": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]}`
- **THEN** events with those seq numbers SHALL be removed from character 12467's events tier

#### Scenario: Delete with stale IDs
- **WHEN** some IDs in the delete list no longer exist (already deleted or never existed)
- **THEN** those IDs SHALL be silently skipped
- **AND** existing IDs SHALL still be deleted

### Requirement: Set verb

The `set` verb SHALL replace an entire resource. Used for initial background writes.

#### Scenario: Set background for character
- **WHEN** mutation is `{"op": "set", "resource": "memory.background", "params": {"character_id": "12467"}, "data": {"traits": [...], "backstory": "...", "connections": [...]}}`
- **THEN** character 12467's background SHALL be replaced with the provided data

### Requirement: Update verb

The `update` verb SHALL apply partial operators to a resource. Supported operators: `$push` (add to list field), `$pull` (remove from list field), `$set` (set field value).

#### Scenario: Update background traits
- **WHEN** mutation is `{"op": "update", "resource": "memory.background", "params": {"character_id": "12467"}, "ops": {"$push": {"traits": "haunted by loss"}, "$pull": {"traits": "jovial"}}}`
- **THEN** "haunted by loss" SHALL be added to traits and "jovial" SHALL be removed

#### Scenario: Update connections
- **WHEN** `$push` targets `connections` with a new connection object
- **THEN** the connection SHALL be appended to the connections list

### Requirement: Mutation response format

The response SHALL be sent on WS topic `state.response` with the same `r` correlation ID. Each mutation result SHALL indicate success or failure independently.

#### Scenario: All mutations succeed
- **WHEN** all mutations in the batch succeed
- **THEN** each result SHALL have `ok: true`

#### Scenario: Partial failure
- **WHEN** one mutation fails (e.g., invalid resource) but others succeed
- **THEN** the failed mutation SHALL have `ok: false` with error message
- **AND** other mutations SHALL still execute and report their status

### Requirement: Atomic compaction pattern

The delete+append pattern for compaction SHALL be supported in a single batch: delete source items by ID, then append compressed results. The sequential execution guarantees ordering.

#### Scenario: Compaction batch (delete events + append summary)
- **WHEN** batch contains `[{"op": "delete", "resource": "memory.events", ...}, {"op": "append", "resource": "memory.summaries", ...}]`
- **THEN** events SHALL be deleted first
- **AND** summary SHALL be appended second
- **AND** both operations target the same character

### Requirement: Supported resources

| Resource | `append` | `delete` | `set` | `update` |
|----------|:--------:|:--------:|:-----:|:--------:|
| `memory.events` | — | ✓ | — | — |
| `memory.summaries` | ✓ | ✓ | — | — |
| `memory.digests` | ✓ | ✓ | — | — |
| `memory.cores` | ✓ | ✓ | — | — |
| `memory.background` | — | — | ✓ | ✓ |

Note: `memory.events` append is exclusively Lua-side (fan-out). Python only deletes events (after compaction).

#### Scenario: Append to memory.events rejected from Python
- **WHEN** Python sends append for `memory.events`
- **THEN** the mutation SHALL succeed (Lua does not distinguish caller)
- **AND** the event SHALL be appended normally

#### Scenario: Unsupported verb for resource
- **WHEN** `set` is attempted on `memory.events`
- **THEN** the mutation SHALL have `ok: false` with error indicating unsupported operation
