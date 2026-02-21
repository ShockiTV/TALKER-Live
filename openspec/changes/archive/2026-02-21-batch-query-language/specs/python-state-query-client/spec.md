# python-state-query-client

## ADDED Requirements

### Requirement: execute_batch method

The `StateQueryClient` SHALL provide `async execute_batch(batch: BatchQuery) -> BatchResult` that sends a single ZMQ message on topic `state.query.batch` and awaits a correlated `state.response`.

#### Scenario: Batch execution sends single message
- **WHEN** `execute_batch(batch)` is called with 4 sub-queries
- **THEN** exactly one ZMQ message SHALL be published
- **AND** one correlated response SHALL be awaited

#### Scenario: Batch timeout raises StateQueryTimeout
- **WHEN** batch response is not received within timeout
- **THEN** `StateQueryTimeout` SHALL be raised with topic `"state.query.batch"`

## MODIFIED Requirements

### Requirement: State Query Client Class

The system MUST provide `StateQueryClient` class with async query methods. During the migration period, existing individual `query_*` methods (query_memories, query_character, query_world_context, query_characters_nearby, query_events_recent) SHALL continue to function but SHOULD log deprecation warnings. After migration is complete, individual methods SHALL be removed in favor of `execute_batch()`.

#### Scenario: Query memories successfully (deprecated path)
- **WHEN** `query_memories("123")` is called during migration
- **THEN** it SHALL function identically to before
- **AND** a deprecation warning SHOULD be logged

#### Scenario: execute_batch is the primary API
- **WHEN** new code needs to fetch state from Lua
- **THEN** it SHALL use `execute_batch()` with a `BatchQuery`

### Requirement: Timeout Handling

The system MUST handle query timeouts with configurable duration. Timeout errors SHALL raise `StateQueryTimeout` (a subclass of `TimeoutError`). For batch queries, the timeout SHALL apply to the entire batch response, not individual sub-queries. The `StateQueryTimeout` exception SHALL include the query topic (either `"state.query.batch"` or the legacy per-topic name for backward compatibility).

#### Scenario: Batch query times out
- **WHEN** `execute_batch(batch)` takes longer than configured timeout
- **THEN** `StateQueryTimeout` SHALL be raised
- **AND** exception SHALL include topic `"state.query.batch"`

#### Scenario: Existing TimeoutError catchers still work
- **WHEN** caller catches `TimeoutError`
- **THEN** `StateQueryTimeout` SHALL be caught (it is a subclass)
- **AND** backward compatibility SHALL be preserved
