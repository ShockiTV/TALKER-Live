## MODIFIED Requirements

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
