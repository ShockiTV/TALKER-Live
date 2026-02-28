# python-state-query-client (delta)

## MODIFIED Requirements

### Requirement: execute_batch method

The `StateQueryClient` SHALL provide `async execute_batch(batch: BatchQuery, *, timeout: float | None = None, session: str | None = None) -> BatchResult` that sends a single message on topic `state.query.batch` and awaits a correlated `state.response`. When `session` is provided, the message SHALL be published only to that session's connection via `WSRouter.publish(..., session=session)`. When `session` is `None`, the message SHALL be broadcast to all connections (backward compatible).

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
