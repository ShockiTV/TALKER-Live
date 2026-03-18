## Requirements

### Requirement: Keycloak as OIDC identity provider

A Keycloak 26 instance SHALL be added to the Docker stack as the sole issuer of player identity tokens. Player accounts SHALL be created manually via the Keycloak admin console. The Keycloak realm SHALL be named `talker` with a single client `talker-client` (confidential OIDC). Player role SHALL be `player`; admin role SHALL be `admin`.

#### Scenario: Player account created by admin
- **WHEN** an admin creates a user in the Keycloak `talker` realm with role `player`
- **THEN** that user can authenticate and receive a JWT with `sub` claim as player_id

#### Scenario: Keycloak accessible at /auth
- **WHEN** a client navigates to `https://{DOMAIN}/auth`
- **THEN** the Keycloak login UI is served via Caddy reverse proxy

### Requirement: Caddy validates JWT via Keycloak JWKS

Caddy SHALL use the `caddy-security` plugin to validate all JWTs issued by Keycloak via the JWKS endpoint. Protected routes SHALL require a valid JWT with role `player` or `admin`. Caddy SHALL inject `X-Player-ID` (from JWT `sub` claim) and `X-Branch` (static string per route) headers before proxying to `talker-*` services.

#### Scenario: Unauthenticated WS connection rejected
- **WHEN** a WebSocket upgrade to `/ws/main` has no valid JWT
- **THEN** Caddy returns 401 before the request reaches `talker-main`

#### Scenario: Valid JWT allows connection
- **WHEN** a WS upgrade has a valid Keycloak JWT with role `player`
- **THEN** Caddy proxies the connection with `X-Player-ID: {sub}` and `X-Branch: main` injected

#### Scenario: Neo4j Browser gated to admin role
- **WHEN** a browser navigates to `/neo4j/` with a player-only JWT
- **THEN** Caddy returns 403
- **WHEN** the same request has an admin JWT
- **THEN** the request is proxied to neo4j:7474

### Requirement: Python reads player_id and branch from headers

The Python WS handler SHALL read `X-Player-ID` and `X-Branch` from the WebSocket upgrade request headers and store them on `ConnectionState`. These SHALL scope all Neo4j Session node creation and queries.

#### Scenario: player_id propagated to session scope
- **WHEN** a WS connection arrives with `X-Player-ID: player1` and `X-Branch: dev`
- **THEN** `ConnectionState.player_id = "player1"` and `ConnectionState.branch = "dev"`
- **AND** all Neo4j Session nodes created in this connection carry `{player_id: "player1", branch: "dev"}`

#### Scenario: Missing headers fall back to defaults
- **WHEN** headers are absent (local dev without Caddy)
- **THEN** `player_id` defaults to `"local"` and `branch` defaults to `"main"`

### Requirement: Lua authenticates via ROPC and passes JWT as query param

The Lua WS connection cannot send custom HTTP headers (pollnet constraint). Instead, Lua authenticates with Keycloak using Resource Owner Password Credentials (ROPC) and appends the resulting JWT as a `?token=` query parameter on the WebSocket URL. This token is then validated by the Python service's `TALKER_TOKENS` store or Caddy upstream.

#### Scenario: ROPC token appended to WS URL
- **WHEN** MCM has non-empty `auth_client_id`, `auth_username`, and `auth_password`
- **THEN** Lua fetches a JWT from Keycloak via ROPC and appends `?token={jwt}` to the WS connect URL

#### Scenario: No token for local dev
- **WHEN** `auth_username` and `auth_password` are empty
- **THEN** the WS connect URL has no `?token=` parameter

#### Scenario: Token fetch failure connects without token
- **WHEN** Keycloak is unreachable or returns an error
- **THEN** the WS connect URL has no `?token=` parameter and connection proceeds unauthenticated
