## MODIFIED Requirements

### Requirement: execute_batch method

The `StateQueryClient` SHALL provide `async execute_batch(batch: BatchQuery, *, timeout: float | None = None, session: str | None = None) -> BatchResult` that sends a single message on topic `state.query.batch` and awaits a correlated `state.response`. The message SHALL be sent via `WSRouter.publish()` with the request ID in the `r` field of the envelope. When `session` is provided, the message SHALL be published only to that session's connection via `WSRouter.publish(..., session=session)`. When `session` is `None`, the message SHALL be broadcast to all connections (backward compatible).

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
