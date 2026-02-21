# python-state-query-client

## Purpose

Python client for requesting state from Lua stores via ZMQ, using the batch query protocol (`state.query.batch`) for all state fetching in a single roundtrip.

## Requirements

### Requirement: State Query Client Class

The system MUST provide `StateQueryClient` class. `execute_batch()` is the primary API for fetching state from Lua. Individual `query_*` methods have been removed in favor of batch queries.

#### Scenario: execute_batch is the primary API
- **WHEN** code needs to fetch state from Lua
- **THEN** it SHALL use `execute_batch()` with a `BatchQuery`
- **AND** results SHALL be accessible via the returned `BatchResult`

### Requirement: execute_batch method

The `StateQueryClient` SHALL provide `async execute_batch(batch: BatchQuery) -> BatchResult` that sends a single ZMQ message on topic `state.query.batch` and awaits a correlated `state.response`.

#### Scenario: Batch execution sends single message
- **WHEN** `execute_batch(batch)` is called with 4 sub-queries
- **THEN** exactly one ZMQ message SHALL be published
- **AND** one correlated response SHALL be awaited

#### Scenario: Batch timeout raises StateQueryTimeout
- **WHEN** batch response is not received within timeout
- **THEN** `StateQueryTimeout` SHALL be raised with topic `"state.query.batch"`

### Requirement: Request-Response Correlation

The system MUST correlate requests and responses using unique request_ids.

#### Scenario: Concurrent queries
- **WHEN** two batch queries are made simultaneously
- **THEN** each gets a unique request_id
- **AND** responses are correctly correlated

### Requirement: Timeout Handling

The system MUST handle query timeouts with configurable duration. Timeout errors SHALL raise `StateQueryTimeout` (a subclass of `TimeoutError`). For batch queries, the timeout SHALL apply to the entire batch response. The `StateQueryTimeout` exception SHALL include the query topic (`"state.query.batch"`) and optionally character_id for diagnostic logging.

#### Scenario: Batch query times out
- **WHEN** `execute_batch(batch)` takes longer than the configured timeout
- **THEN** `StateQueryTimeout` SHALL be raised
- **AND** exception SHALL include topic `"state.query.batch"`

#### Scenario: Existing TimeoutError catchers still work
- **WHEN** caller catches `TimeoutError`
- **THEN** `StateQueryTimeout` SHALL be caught (it is a subclass)
- **AND** backward compatibility SHALL be preserved
