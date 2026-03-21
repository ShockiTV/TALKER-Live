# python-keycloak-auth

## Purpose

An `httpx.Auth` subclass that authenticates outbound HTTP requests from `talker_service` to JWT-gated VPS APIs using Keycloak ROPC (Resource Owner Password Credentials) grant, with token caching, proactive refresh, and lazy initialization from credentials received via `config.sync`.

## Requirements

### Requirement: KeycloakAuth httpx.Auth subclass

A `KeycloakAuth` class in `talker_service/src/talker_service/auth/keycloak.py` SHALL implement the `httpx.Auth` protocol. It SHALL accept `token_url`, `client_id`, `client_secret`, `username`, and `password` as constructor arguments. It SHALL add a `Bearer` token to the `Authorization` header of every outgoing request.

#### Scenario: Auth header added to outgoing request

- **WHEN** an `httpx.AsyncClient` is created with `auth=KeycloakAuth(token_url, client_id, client_secret, username, password)`
- **AND** a GET request is made through the client
- **THEN** the request SHALL include header `Authorization: Bearer <access_token>`

#### Scenario: Auth instance created with all credentials

- **WHEN** `KeycloakAuth` is instantiated with `token_url="https://hub/auth/realms/talker/protocol/openid-connect/token"`, `client_id="talker-client"`, `client_secret="secret"`, `username="player1"`, `password="pass123"`
- **THEN** the instance SHALL store all credentials for subsequent token requests

### Requirement: Lazy ROPC token acquisition

`KeycloakAuth` SHALL NOT fetch a token at construction time. The first token SHALL be acquired lazily on the first HTTP request that requires authentication. The ROPC grant SHALL POST to the `token_url` with `grant_type=password`, `client_id`, `client_secret`, `username`, and `password` as form-encoded body.

#### Scenario: No token request at construction

- **WHEN** `KeycloakAuth` is instantiated
- **THEN** no HTTP request to the token endpoint SHALL be made

#### Scenario: First request triggers ROPC grant

- **WHEN** the first outgoing HTTP request passes through `KeycloakAuth`
- **AND** no cached token exists
- **THEN** `KeycloakAuth` SHALL POST to the token endpoint with `grant_type=password` and the stored credentials
- **AND** use the returned `access_token` in the request's `Authorization` header

#### Scenario: ROPC response parsed correctly

- **WHEN** the token endpoint returns `{"access_token": "abc", "refresh_token": "def", "expires_in": 300, "refresh_expires_in": 1800}`
- **THEN** `KeycloakAuth` SHALL cache `access_token="abc"`, `refresh_token="def"`, compute expiry timestamps from `expires_in` and `refresh_expires_in`

### Requirement: Token caching with expiry tracking

`KeycloakAuth` SHALL cache the `access_token` and `refresh_token` along with their expiry timestamps. Subsequent requests SHALL reuse the cached `access_token` without contacting the token endpoint, as long as the access token has not expired.

#### Scenario: Cached token reused for subsequent requests

- **WHEN** a valid `access_token` is cached with expiry in the future
- **AND** a second HTTP request passes through `KeycloakAuth`
- **THEN** the cached token SHALL be used without a new token request

#### Scenario: Expired access token not reused

- **WHEN** the cached `access_token` has expired
- **AND** a new HTTP request passes through `KeycloakAuth`
- **THEN** `KeycloakAuth` SHALL NOT use the expired access token directly

### Requirement: Proactive refresh via refresh_token

When the cached `access_token` has expired but the `refresh_token` is still valid, `KeycloakAuth` SHALL attempt a token refresh using `grant_type=refresh_token` before falling back to a full ROPC grant.

#### Scenario: Expired access token refreshed via refresh_token

- **WHEN** the `access_token` has expired
- **AND** the `refresh_token` has NOT expired
- **THEN** `KeycloakAuth` SHALL POST to the token endpoint with `grant_type=refresh_token` and `refresh_token`
- **AND** cache the new tokens from the response

#### Scenario: Both tokens expired triggers full ROPC

- **WHEN** both `access_token` and `refresh_token` have expired
- **THEN** `KeycloakAuth` SHALL perform a full ROPC grant with `grant_type=password`
- **AND** cache the new tokens

### Requirement: 401 retry with token refresh

If an upstream service returns HTTP 401 despite a cached token, `KeycloakAuth` SHALL clear the token cache and retry the request once with a freshly acquired token.

#### Scenario: 401 triggers token refresh and retry

- **WHEN** an HTTP request returns 401
- **AND** a cached token was used
- **THEN** `KeycloakAuth` SHALL clear the token cache
- **AND** acquire a new token (via refresh or ROPC)
- **AND** retry the original request once with the new token

#### Scenario: Second 401 not retried

- **WHEN** a retry request also returns 401
- **THEN** `KeycloakAuth` SHALL NOT retry again
- **AND** the 401 response SHALL be returned to the caller

### Requirement: Token acquisition failure handling

If the token endpoint is unreachable or returns an error, `KeycloakAuth` SHALL log the error and allow the request to proceed without an `Authorization` header. This prevents cascading failures when Keycloak is temporarily unavailable.

#### Scenario: Token endpoint unreachable

- **WHEN** the token endpoint times out or returns a connection error
- **THEN** `KeycloakAuth` SHALL log the error at WARNING level
- **AND** the outgoing request SHALL proceed without an `Authorization` header

#### Scenario: Token endpoint returns error response

- **WHEN** the token endpoint returns HTTP 400 with `{"error": "invalid_grant"}`
- **THEN** `KeycloakAuth` SHALL log the error details at WARNING level
- **AND** the outgoing request SHALL proceed without an `Authorization` header

### Requirement: No auth when credentials are absent

When `KeycloakAuth` is not instantiated (credentials are empty or `service_type` is "local"), the `httpx.AsyncClient` SHALL be created without an `auth` parameter. No authentication headers SHALL be added to outbound requests.

#### Scenario: Local service type uses no auth

- **WHEN** `service_type` is "local"
- **THEN** the shared `httpx.AsyncClient` SHALL be created without `auth`
- **AND** outgoing requests to TTS/STT/embed services SHALL have no `Authorization` header

#### Scenario: Empty credentials use no auth

- **WHEN** `auth_username` and `auth_password` are empty strings
- **THEN** `KeycloakAuth` SHALL NOT be instantiated
- **AND** the shared `httpx.AsyncClient` SHALL be created without `auth`

### Requirement: Shared authenticated httpx.AsyncClient

A single `httpx.AsyncClient` per session SHALL be created with `auth=KeycloakAuth(...)` when remote auth is configured, or without `auth` when local. This client SHALL be injected into `TTSRemoteClient`, `EmbeddingClient`, and the OpenAI SDK (via `http_client` parameter for `WhisperAPIProvider`).

#### Scenario: TTS client uses shared authenticated client

- **WHEN** `service_type` is "remote" and auth credentials are configured
- **THEN** `TTSRemoteClient` SHALL use the shared `httpx.AsyncClient` with `KeycloakAuth`
- **AND** TTS requests SHALL include JWT Bearer authentication

#### Scenario: STT client uses shared authenticated client

- **WHEN** `service_type` is "remote" and auth credentials are configured
- **THEN** `WhisperAPIProvider` SHALL be created with `http_client=httpx.AsyncClient(auth=keycloak_auth)`
- **AND** STT API calls SHALL include JWT Bearer authentication

#### Scenario: Embedding client uses shared authenticated client

- **WHEN** `service_type` is "remote" and auth credentials are configured
- **THEN** `EmbeddingClient` SHALL use the shared `httpx.AsyncClient` with `KeycloakAuth`
- **AND** embedding requests SHALL include JWT Bearer authentication
