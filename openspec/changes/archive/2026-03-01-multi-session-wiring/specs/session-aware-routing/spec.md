## MODIFIED Requirements

### Requirement: Handler dispatch includes session_id

All registered message handlers SHALL be called with `(payload, session_id)` instead of `(payload)`. The router SHALL resolve the session_id from the connection that sent the message before dispatching to the handler. The `MessageHandler` type alias SHALL be `Callable[[dict[str, Any], str], Awaitable[None]]`.

#### Scenario: Handler receives session_id

- **WHEN** a message `{"t": "game.event", "p": {...}}` arrives from a connection with session_id "alice"
- **THEN** the `game.event` handler SHALL be called with `(payload, "alice")`

#### Scenario: Handler receives default session in no-auth mode

- **WHEN** auth is disabled
- **AND** a message arrives
- **THEN** the handler SHALL be called with `(payload, "__default__")`

### Requirement: Targeted publish by session

`WSRouter.publish()` SHALL accept an optional `session: str | None` parameter. When `session` is provided, the message SHALL be sent only to the connection associated with that session_id. When `session` is `None`, the message SHALL be broadcast to all connections. When `session` is provided but the session has no active connection, the message SHALL be buffered in the session's outbox via `SessionRegistry`.

#### Scenario: Publish to specific session

- **WHEN** `publish("dialogue.display", payload, session="alice")` is called
- **AND** session "alice" has an active connection
- **THEN** the message SHALL be sent only to alice's connection
- **AND** other sessions SHALL NOT receive the message

#### Scenario: Publish broadcast when session is None

- **WHEN** `publish("topic", payload)` is called without session parameter
- **THEN** the message SHALL be sent to all active connections

#### Scenario: Publish to disconnected session buffers in outbox

- **WHEN** `publish("dialogue.display", payload, session="alice")` is called
- **AND** session "alice" has no active connection
- **THEN** the message SHALL be added to alice's outbox
- **AND** `publish()` SHALL return `True` (message was accepted)
