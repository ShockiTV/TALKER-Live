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

When authentication is enabled, `WSRouter` SHALL extract the `token` query parameter from the WebSocket upgrade request before calling `accept()`. If the token is absent or not in the token store, the connection SHALL be closed with code 4001.

#### Scenario: Valid token accepted

- **WHEN** a client connects with `?token=token-abc`
- **AND** `token-abc` is in the token store
- **THEN** the connection is accepted

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

When `TALKER_TOKENS` is unset, ALL WebSocket connections SHALL be accepted without token validation. No check is performed. This is the default behavior for local installations.

#### Scenario: No token required in local mode

- **WHEN** `TALKER_TOKENS` is not set
- **AND** a client connects without any `?token=` parameter
- **THEN** the connection is accepted

### Requirement: Token does not appear in logs

Token values SHALL NOT be logged at any level. Only the token name (if resolved) MAY be logged for audit purposes.

#### Scenario: Token value excluded from logs

- **WHEN** a connection attempt occurs (valid or invalid)
- **THEN** no log line contains the raw token string value
