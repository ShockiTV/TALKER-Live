## ADDED Requirements

### Requirement: Configure Keycloak refresh-token auth

The auth client SHALL accept configuration via three parameters: `token_url` (string), `client_id` (string), and `refresh_token` (string). When all three are non-empty, refresh-token auth SHALL be considered enabled. When any is empty or nil, auth SHALL be considered disabled and token operations SHALL return nil without error.

#### Scenario: All values configured enables auth

- **WHEN** `keycloak_client.configure("https://domain/auth/realms/talker/protocol/openid-connect/token", "talker-game", "rt_123")` is called
- **THEN** auth is enabled
- **AND** subsequent `fetch_token()` calls SHALL attempt token exchange

#### Scenario: Missing refresh token disables auth

- **WHEN** `keycloak_client.configure("https://domain/auth/...", "talker-game", "")` is called
- **THEN** auth is disabled
- **AND** `fetch_token()` SHALL return `nil`
- **AND** no HTTP request SHALL be made

#### Scenario: All empty disables auth (local dev)

- **WHEN** `keycloak_client.configure("", "", "")` is called
- **THEN** auth is disabled
- **AND** `get_cached_token()` SHALL return `nil`

### Requirement: Fetch access token via refresh-token grant

When auth is enabled, `fetch_token()` SHALL perform an HTTP POST to the configured `token_url` with body `grant_type=refresh_token&client_id=<id>&refresh_token=<token>` and header `Content-Type: application/x-www-form-urlencoded`. The function SHALL parse JSON response fields `access_token` and `expires_in`. On success, it SHALL cache access token and expiry and return the access token string. On failure, it SHALL return `nil` and an error message string.

#### Scenario: Successful token exchange

- **WHEN** `fetch_token()` is called with valid configuration
- **AND** Keycloak responds with `{"access_token": "eyJ...", "expires_in": 300, "token_type": "Bearer"}`
- **THEN** the function SHALL return `"eyJ..."`
- **AND** the access token SHALL be cached with expiry time

#### Scenario: Refresh token rotation response

- **WHEN** Keycloak responds with `{"access_token": "eyJ...", "expires_in": 300, "refresh_token": "rt_new"}`
- **THEN** `fetch_token()` SHALL update the stored refresh token in memory to `"rt_new"`
- **AND** later exchanges SHALL use the rotated refresh token

#### Scenario: Keycloak returns error

- **WHEN** `fetch_token()` is called
- **AND** Keycloak responds with `{"error": "invalid_grant", "error_description": "Token is not active"}`
- **THEN** the function SHALL return `nil, "invalid_grant: Token is not active"`

#### Scenario: HTTP request fails or times out

- **WHEN** `fetch_token()` is called
- **AND** the HTTP request does not complete within 5 seconds
- **THEN** the function SHALL return `nil, "token fetch timeout"`

#### Scenario: Auth disabled returns nil

- **WHEN** auth is not configured
- **AND** `fetch_token()` is called
- **THEN** the function SHALL return `nil` without making any HTTP request

### Requirement: Token caching with expiry awareness

The auth client SHALL cache the most recently fetched access token along with expiry timestamp (`os.time() + expires_in`). `get_cached_token()` SHALL return cached token when more than 60 seconds remain before expiry. If expired or within 60-second safety margin, `get_cached_token()` SHALL return `nil`.

#### Scenario: Cached token returned when valid

- **WHEN** a token was fetched with `expires_in=300`
- **AND** 100 seconds have elapsed
- **THEN** `get_cached_token()` SHALL return cached token string

#### Scenario: Cached token rejected near expiry

- **WHEN** a token was fetched with `expires_in=300`
- **AND** 250 seconds have elapsed (50 seconds remaining)
- **THEN** `get_cached_token()` SHALL return `nil`

#### Scenario: No cached token returns nil

- **WHEN** no token has been fetched
- **THEN** `get_cached_token()` SHALL return `nil`

### Requirement: Clear cached state

`clear()` SHALL remove cached token/expiry and reset configured values. After `clear()`, `get_cached_token()` SHALL return `nil` and `fetch_token()` SHALL return `nil` (auth disabled).

#### Scenario: Clear removes cached token

- **WHEN** a token is cached
- **AND** `clear()` is called
- **THEN** `get_cached_token()` SHALL return `nil`

### Requirement: Sensitive token values not logged

The auth client SHALL NOT log `refresh_token` or access token values at any log level. `client_id` and `token_url` MAY be logged at debug level.

#### Scenario: Successful fetch logs without secrets

- **WHEN** a token is fetched successfully
- **THEN** logs MAY contain `token_url` and `client_id`
- **AND** logs SHALL NOT contain `refresh_token` value
- **AND** logs SHALL NOT contain access token value

### Requirement: MCM configuration fields

The MCM UI SHALL provide two text input fields for automated auth in the VPS/Remote section: `auth_client_id` and `auth_refresh_token`. `interface.config` SHALL expose getters `config.auth_client_id()` and `config.auth_refresh_token()`.

#### Scenario: Config getters return MCM values

- **WHEN** `auth_client_id` is set to `"talker-game"` in MCM
- **THEN** `config.auth_client_id()` SHALL return `"talker-game"`

#### Scenario: Config getters return empty string when unset

- **WHEN** `auth_refresh_token` is not configured
- **THEN** `config.auth_refresh_token()` SHALL return `""`

### Requirement: WS connection uses refresh-token access token

When `auth_client_id` and `auth_refresh_token` are configured, `talker_ws_integration` SHALL derive token endpoint URL from `service_url` origin and call `keycloak_client.get_cached_token()` or `keycloak_client.fetch_token()` before building WS URL. The token SHALL be appended as `?token=<access_token>`. When automated auth is not configured, existing `ws_bearer_token` fallback SHALL be used. When neither is configured, URL SHALL have no token parameter.

#### Scenario: Derived token URL and access token appended

- **WHEN** `service_url` is `wss://domain/ws/dev`
- **AND** `auth_client_id` and `auth_refresh_token` are configured
- **AND** `keycloak_client.fetch_token()` returns `"eyJ..."`
- **THEN** token URL `https://domain/auth/realms/talker/protocol/openid-connect/token` is used for exchange
- **AND** WS URL SHALL be `wss://domain/ws/dev?token=eyJ...`

#### Scenario: Fallback to static bearer token

- **WHEN** automated auth is not configured
- **AND** `ws_bearer_token` is set to `"static-token"`
- **THEN** WS URL SHALL be `wss://domain/ws/dev?token=static-token`

#### Scenario: No token when nothing configured

- **WHEN** neither automated auth nor `ws_bearer_token` is configured
- **THEN** WS URL SHALL be `ws://127.0.0.1:5557/ws`

### Requirement: Token refresh on reconnect

When bridge channel reconnects after disconnection, it SHALL attempt `keycloak_client.fetch_token()` before opening new WS connection.

#### Scenario: Reconnect fetches fresh token

- **WHEN** WS drops and bridge attempts reconnect
- **THEN** `keycloak_client.fetch_token()` SHALL be called before `ws_client.open(url)`
- **AND** new URL SHALL use freshly fetched access token

#### Scenario: Reconnect continues without refreshed token

- **WHEN** WS drops
- **AND** `keycloak_client.fetch_token()` returns `nil`
- **THEN** reconnect SHALL still attempt with fallback token/no token
- **AND** backoff retry loop SHALL continue
