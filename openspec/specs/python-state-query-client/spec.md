# python-state-query-client

## Purpose

Python client for requesting state from Lua stores via WebSocket, using the batch query protocol (`state.query.batch`) for all state fetching in a single roundtrip.

## Requirements

### Requirement: execute_batch method

The `StateQueryClient` SHALL provide `async execute_batch(batch: BatchQuery, *, timeout: float | None = None, session: str | None = None) -> BatchResult` that sends a single message on topic `state.query.batch` and awaits a correlated `state.response`. The message SHALL be sent via `WSRouter.publish()` with the request ID in the `r` field of the envelope. The response is resolved when `WSRouter` receives a frame with the matching `r` field and sets the corresponding `asyncio.Future`. When `session` is provided, the message SHALL be published only to that session's connection via `WSRouter.publish(..., session=session)`. When `session` is `None`, the message SHALL be broadcast to all connections (backward compatible).

#### Scenario: Batch execution sends single message
- **WHEN** `execute_batch(batch)` is called with 4 sub-queries
- **THEN** exactly one WS frame SHALL be sent with `t = "state.query.batch"` and a unique `r` field
- **AND** one correlated response SHALL be awaited via the `r` field future

#### Scenario: Batch execution routes to specific session

- **WHEN** `execute_batch(batch, session="alice")` is called
- **THEN** the `state.query.batch` message SHALL be sent only to alice's connection
- **AND** one correlated response SHALL be awaited via the `r` field future

#### Scenario: Batch execution broadcasts when session is None

- **WHEN** `execute_batch(batch)` is called without session parameter
- **THEN** the `state.query.batch` message SHALL be sent to all connections

#### Scenario: Batch timeout raises StateQueryTimeout
- **WHEN** the batch response is not received within the configured timeout
- **THEN** `StateQueryTimeout` SHALL be raised with topic `"state.query.batch"`
- **AND** the pending future SHALL be cancelled and removed from `pending_requests`

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
