## MODIFIED Requirements

### Requirement: execute_batch method

The `StateQueryClient` SHALL provide `async execute_batch(batch: BatchQuery) -> BatchResult` that sends a single message on topic `state.query.batch` and awaits a correlated `state.response`. The message SHALL be sent via `WSRouter.publish()` with the request ID in the `r` field of the envelope. The response is resolved when `WSRouter` receives a frame with the matching `r` field and sets the corresponding `asyncio.Future`.

#### Scenario: Batch execution sends single message

- **WHEN** `execute_batch(batch)` is called with 4 sub-queries
- **THEN** exactly one WS frame SHALL be sent with `t = "state.query.batch"` and a unique `r` field
- **AND** one correlated response SHALL be awaited via the `r` field future

#### Scenario: Batch timeout raises StateQueryTimeout

- **WHEN** the batch response is not received within the configured timeout
- **THEN** `StateQueryTimeout` SHALL be raised with topic `"state.query.batch"`
- **AND** the pending future SHALL be cancelled and removed from `pending_requests`

## REMOVED Requirements

### Requirement: State Query Client Class (ZMQ transport)

**Reason**: `StateQueryClient` no longer uses ZMQ. It publishes via `WSRouter.publish()` and receives responses via `r`-field routing in `WSRouter._process_message`. The ZMQ-based `pending_requests` registration via a named `state.response` handler is deleted.

**Migration**: `StateQueryClient.__init__` now accepts a `WSRouter` instead of a `ZMQRouter`. The `execute_batch` call signature is unchanged. Tests that mock ZMQ must be updated to mock `WSRouter.publish` and inject WS response frames.
