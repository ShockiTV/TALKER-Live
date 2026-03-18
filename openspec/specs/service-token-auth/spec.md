# service-token-auth

## Purpose

Static token authentication for the WebSocket endpoint. Tokens are pre-issued and passed via query parameter. Authentication is disabled (no-auth local mode) when not configured.

## Requirements

### Requirement: Parse TALKER_TOKENS environment variable

On startup, the service SHALL read `TALKER_TOKENS` from the environment. The format is `name:token,name2:token2,...`. Each pair SHALL be split on the first `:`. Leading/trailing whitespace in names and tokens SHALL be stripped. If `TALKER_TOKENS` is unset or empty, authentication is disabled.

#### Scenario: Valid TALKER_TOKENS parsed

- **WHEN** `TALKER_TOKENS=alice:token-abc,bob:token-xyz` is set
- **THEN** the token store contains `{"alice": "token-abc", "bob": "token-xyz"}`

#### Scenario: TALKER_TOKENS unset disables auth

- **WHEN** `TALKER_TOKENS` is not set
- **THEN** the token store is empty
- **AND** all WebSocket connections are accepted without a token

#### Scenario: Malformed entry logged and skipped

- **WHEN** `TALKER_TOKENS=alice:token-abc,badentry` is set
- **THEN** `alice:token-abc` is stored
- **AND** `badentry` is logged as a warning and skipped

### Requirement: Token validation on WebSocket upgrade

When authentication is enabled, `WSRouter` SHALL extract the `token` query parameter from the WebSocket upgrade request before calling `accept()`. If the token is absent or not in the token store, the connection SHALL be closed with code 4001. On successful validation, the token SHALL be resolved to its corresponding name (the key in the TALKER_TOKENS map), which SHALL be used as the `session_id` for the connection.

When the token is a JWT (three dot-separated base64 segments), the router SHALL also attempt to decode the payload (without signature verification) to extract `sub` or `preferred_username` claims for use as `player_id`. This supports tokens issued by Keycloak via refresh-token exchange, where `sub` maps to the player account.

#### Scenario: Valid static token accepted and session_id assigned

- **WHEN** `TALKER_TOKENS=alice:tok-abc` is configured
- **AND** a client connects with `?token=tok-abc`
- **THEN** the connection is accepted
- **AND** the connection is assigned `session_id = "alice"`

#### Scenario: Valid JWT token accepted via TALKER_TOKENS

- **WHEN** `TALKER_TOKENS` is not configured (auth disabled)
- **AND** a client connects with `?token=eyJhbGci...` (a valid JWT)
- **THEN** the connection is accepted (no-auth mode)
- **AND** the JWT payload's `sub` claim SHALL be used as `player_id` if present

#### Scenario: Invalid token rejected with code 4001

- **WHEN** `TALKER_TOKENS` is configured
- **AND** a client connects with `?token=wrong-token`
- **AND** `wrong-token` is not in the token store
- **THEN** the connection is closed with code 4001
- **AND** no messages are processed

#### Scenario: Missing token rejected when auth is enabled

- **WHEN** `TALKER_TOKENS` is configured
- **AND** a client connects without a `?token=` parameter
- **THEN** the connection is closed with code 4001

### Requirement: No-auth local mode

When `TALKER_TOKENS` is unset, ALL WebSocket connections SHALL be accepted without token validation. No check is performed. All connections SHALL be assigned the constant `session_id = "__default__"`. This is the default behavior for local installations.

#### Scenario: No token required in local mode

- **WHEN** `TALKER_TOKENS` is not set
- **AND** a client connects without any `?token=` parameter
- **THEN** the connection is accepted
- **AND** the connection is assigned `session_id = "__default__"`

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

### Requirement: Token does not appear in logs

Token values SHALL NOT be logged at any level. Only the token name (if resolved) MAY be logged for audit purposes.

#### Scenario: Token value excluded from logs

- **WHEN** a connection attempt occurs (valid or invalid)
- **THEN** no log line contains the raw token string value
