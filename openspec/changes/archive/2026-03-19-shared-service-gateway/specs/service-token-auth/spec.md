# service-token-auth (delta)

## MODIFIED Requirements

### Requirement: Token validation on WebSocket upgrade

When authentication is enabled, `WSRouter` SHALL extract the `token` query parameter from the WebSocket upgrade request before calling `accept()`. If the token is absent or not in the token store, the connection SHALL be closed with code 4001. On successful validation, the token SHALL be resolved to its corresponding name (the key in the TALKER_TOKENS map), which SHALL be used as the `session_id` for the connection.

When the token is a JWT (three dot-separated base64 segments), the router SHALL also attempt to decode the payload (without signature verification) to extract `sub` or `preferred_username` claims for use as `player_id`. This supports tokens issued by Keycloak via refresh-token exchange, where `sub` maps to the player account.

When authentication is enabled AND auth credentials are present in the session's `ConfigMirror` (received via `config.sync`), the session SHALL store these credentials for use by `KeycloakAuth` when making outbound HTTP API calls. The credentials (`auth_username`, `auth_password`, `auth_client_id`, `auth_client_secret`) SHALL be available to the session's authenticated `httpx.AsyncClient`.

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

#### Scenario: Auth credentials from config.sync stored for outbound HTTP

- **WHEN** session "alice" sends `config.sync` with `auth_username`, `auth_password`, `auth_client_id`, `auth_client_secret`
- **THEN** the session's `ConfigMirror` SHALL store these credentials
- **AND** they SHALL be available for `KeycloakAuth` instantiation on the first outbound HTTP call

## ADDED Requirements

### Requirement: Lua skips ROPC when service type is local

When the MCM `service_type` is set to "local" (0), `keycloak_client.lua` SHALL skip the ROPC token exchange entirely. The WebSocket connect URL SHALL have no `?token=` parameter. ROPC SHALL only be performed when `service_type` is "remote" (1) AND `auth_username` and `auth_password` are non-empty.

#### Scenario: Local service type connects without token

- **WHEN** MCM `service_type` is 0 (Local)
- **THEN** the WS connect URL SHALL be `ws://127.0.0.1:<port>/ws` with no `?token=` parameter
- **AND** no ROPC request SHALL be made to Keycloak

#### Scenario: Remote service type with credentials performs ROPC

- **WHEN** MCM `service_type` is 1 (Remote)
- **AND** `auth_username` and `auth_password` are non-empty
- **THEN** Lua SHALL perform ROPC and append `?token=<jwt>` to the WS URL

#### Scenario: Remote service type without credentials connects unauthenticated

- **WHEN** MCM `service_type` is 1 (Remote)
- **AND** `auth_username` or `auth_password` is empty
- **THEN** the WS connect URL SHALL have no `?token=` parameter
