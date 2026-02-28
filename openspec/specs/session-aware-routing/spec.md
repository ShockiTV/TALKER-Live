# session-aware-routing

## Purpose

WSRouter tracks session identity per WebSocket connection, dispatches inbound messages with session context to handlers, and publishes outbound messages to targeted sessions.

## Requirements

### Requirement: Session identity from connection

When a WebSocket client connects, the router SHALL resolve a `session_id` from the auth token. When `TALKER_TOKENS` is configured, the token name (the key in name:token pairs) SHALL be used as the `session_id`. When auth is disabled (no `TALKER_TOKENS`), a constant `"__default__"` session_id SHALL be assigned to all connections.

#### Scenario: Authenticated connection gets session_id from token name

- **WHEN** `TALKER_TOKENS=alice:tok-abc,bob:tok-xyz` is configured
- **AND** a client connects with `?token=tok-abc`
- **THEN** the connection SHALL be associated with `session_id = "alice"`

#### Scenario: No-auth mode uses default session_id

- **WHEN** `TALKER_TOKENS` is not configured
- **AND** a client connects without a token
- **THEN** the connection SHALL be associated with `session_id = "__default__"`

#### Scenario: Session_id is stable across reconnects

- **WHEN** a client connects with `?token=tok-abc` (session_id "alice")
- **AND** disconnects
- **AND** reconnects with the same `?token=tok-abc`
- **THEN** the same `session_id = "alice"` SHALL be assigned

### Requirement: Handler dispatch includes session_id

All registered message handlers SHALL be called with `(payload, session_id)` instead of `(payload)`. The router SHALL resolve the session_id from the connection that sent the message before dispatching to the handler.

#### Scenario: Handler receives session_id

- **WHEN** a message `{"t": "game.event", "p": {...}}` arrives from a connection with session_id "alice"
- **THEN** the `game.event` handler SHALL be called with `(payload, "alice")`

#### Scenario: Handler receives default session in no-auth mode

- **WHEN** auth is disabled
- **AND** a message arrives
- **THEN** the handler SHALL be called with `(payload, "__default__")`

### Requirement: Targeted publish by session

`WSRouter.publish()` SHALL accept an optional `session: str | None` parameter. When `session` is provided, the message SHALL be sent only to the connection associated with that session_id. When `session` is `None`, the message SHALL be broadcast to all connections.

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

### Requirement: Session context tracking

The router SHALL maintain a `SessionContext` per session_id that holds the active WebSocket connection (if any), session metadata, and a reference to the session's outbox. The SessionContext SHALL persist after disconnection to enable reconnection to the same session.

#### Scenario: Session context persists after disconnect

- **WHEN** session "alice" disconnects
- **THEN** the SessionContext for "alice" SHALL remain
- **AND** the active connection field SHALL be set to None

#### Scenario: Reconnect replaces connection atomically

- **WHEN** session "alice" reconnects with a new WebSocket
- **THEN** the new connection SHALL replace the old one in SessionContext
- **AND** the outbox SHALL begin draining to the new connection

### Requirement: Connection-to-session reverse lookup

The router SHALL maintain a reverse mapping from WebSocket connection to session_id for efficient lookup during message processing and disconnect handling.

#### Scenario: Message sender identified by connection

- **WHEN** a message arrives on a WebSocket connection
- **THEN** the router SHALL resolve the session_id in O(1) time via the reverse mapping
