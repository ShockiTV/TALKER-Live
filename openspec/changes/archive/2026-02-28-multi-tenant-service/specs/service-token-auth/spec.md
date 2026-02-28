# service-token-auth (delta)

## MODIFIED Requirements

### Requirement: Token validation on WebSocket upgrade

When authentication is enabled, `WSRouter` SHALL extract the `token` query parameter from the WebSocket upgrade request before calling `accept()`. If the token is absent or not in the token store, the connection SHALL be closed with code 4001. On successful validation, the token SHALL be resolved to its corresponding name (the key in the TALKER_TOKENS map), which SHALL be used as the `session_id` for the connection.

#### Scenario: Valid token accepted and session_id assigned

- **WHEN** `TALKER_TOKENS=alice:tok-abc` is configured
- **AND** a client connects with `?token=tok-abc`
- **THEN** the connection is accepted
- **AND** the connection is assigned `session_id = "alice"`

#### Scenario: Invalid token rejected with code 4001

- **WHEN** a client connects with `?token=wrong-token`
- **AND** `wrong-token` is not in the token store
- **THEN** the connection is closed with code 4001
- **AND** no messages are processed

#### Scenario: Missing token rejected when auth is enabled

- **WHEN** `TALKER_TOKENS` is configured
- **AND** a client connects without a `?token=` parameter
- **THEN** the connection is closed with code 4001

### Requirement: No-auth local mode

When `TALKER_TOKENS` is unset, ALL WebSocket connections SHALL be accepted without token validation. No check is performed. All connections SHALL be assigned the constant `session_id = "__default__"`.

#### Scenario: No token required in local mode

- **WHEN** `TALKER_TOKENS` is not set
- **AND** a client connects without any `?token=` parameter
- **THEN** the connection is accepted
- **AND** the connection is assigned `session_id = "__default__"`

## ADDED Requirements

### Requirement: Reverse token lookup

The token store SHALL support reverse lookup: given a token value, resolve the associated name. This is used to derive session_id from the token presented at connection time.

#### Scenario: Token value resolves to name

- **WHEN** `TALKER_TOKENS=alice:tok-abc,bob:tok-xyz` is configured
- **AND** a token value `tok-abc` is looked up
- **THEN** the result SHALL be `"alice"`

#### Scenario: Unknown token value returns None

- **WHEN** a token value `unknown-tok` is looked up
- **THEN** the result SHALL be `None`

### Requirement: Session lifecycle logging

On connection, the router SHALL log the session_id (not the token value) at INFO level. On disconnection, the router SHALL log the session_id and whether the session has pending outbox messages.

#### Scenario: Connect logged with session_id

- **WHEN** session "alice" connects
- **THEN** an INFO log SHALL include `session_id=alice` and total connection count
- **AND** the log SHALL NOT contain the token value

#### Scenario: Disconnect logged with outbox status

- **WHEN** session "alice" disconnects with 3 messages in outbox
- **THEN** an INFO log SHALL include `session_id=alice` and `outbox_pending=3`
