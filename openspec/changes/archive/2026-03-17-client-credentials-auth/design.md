## Context

The game client connects to the VPS via `wss://domain/ws/<branch>?token=<jwt>`. Caddy validates the JWT against Keycloak JWKS before proxying to talker_service. Currently, the user manually obtains a Keycloak access token (5-min TTL) via browser and pastes it into MCM as `ws_bearer_token`. This breaks within minutes.

pollnet's `http_post()` supports custom headers and request bodies, so Lua can perform OAuth2 token exchanges directly. The bridge channel already has reconnect logic with exponential backoff. The Caddy config already injects `Authorization: Bearer` from the `?token=` query param.

## Goals / Non-Goals

**Goals:**
- Automate token acquisition: game fetches its own access token on load and before each WS connect
- Preserve per-player identity claims (`sub`) in JWTs
- Use OAuth2 refresh-token exchange against Keycloak with only two MCM inputs
- Cache the token and refresh it proactively (before expiry)
- Maintain backward compatibility: local dev (no auth fields set) works exactly as before
- Keep the `?token=` query param transport mechanism (Caddy already handles it)

**Non-Goals:**
- Browser/device-code UX inside the game UI
- Modifying the Python service auth logic (unchanged)
- Modifying Caddy's JWT validation (already working with query param injection)

## Decisions

### 1. OAuth2 refresh-token exchange

**Choice**: Exchange a stored refresh token for short-lived access tokens before connect.

**Rationale**: This keeps identity bound to a user account while still automating token refresh. The game only needs `client_id` and `refresh_token` in MCM. Each fetch returns a fresh access token used for the WebSocket URL.

**Alternatives considered**:
- *Client credentials*: Automates refresh but collapses identity into a service account when shared credentials are used.
- *Long TTL access tokens*: Still expires and does not solve lifecycle/reconnect behavior.
- *Static shared secrets (TALKER_TOKENS)*: Bypasses Keycloak and JWKS validation.

### 2. New `infra/auth/keycloak_client.lua` module

**Choice**: Dedicated auth client module in the infra layer, not embedded in `talker_ws_integration.script`.

**Rationale**: Clean architecture — auth is an infrastructure concern. The module is testable in isolation (pollnet HTTP is already mockable). The WS integration script calls it before connecting, keeping the connection lifecycle code clean.

**Interface**:
```
keycloak_client.configure(token_url, client_id, refresh_token)
keycloak_client.fetch_token() → token_string or nil, error
keycloak_client.get_cached_token() → token_string or nil
keycloak_client.clear()
```

### 3. Blocking HTTP for token fetch

**Choice**: Use pollnet's synchronous-style HTTP polling (poll until response or timeout) for the token exchange, called *before* opening the WS connection.

**Rationale**: The token must be available before `ws_client.open(url)` is called. pollnet HTTP is non-blocking underneath but the poll loop blocks the Lua thread. This is acceptable because:
- It happens once at game load and on reconnect (not every tick)
- Keycloak token endpoint responds in <100ms typically
- There's already a blocking window during game load (state loading, persistence, etc.)

A hard timeout (5 seconds) prevents hanging if Keycloak is unreachable.

### 4. Token caching with proactive refresh

**Choice**: Cache the access token and its `expires_in` timestamp. On each `get_cached_token()` call, check if the token is within a safety margin (60 seconds) of expiry and return nil to trigger a refresh.

**Rationale**: Avoids unnecessary HTTP calls while ensuring the token is always fresh when used. The bridge channel's reconnect path naturally calls `get_service_url()` → `get_cached_token()` → `fetch_token()` when needed.

Additionally, when Keycloak returns a new `refresh_token`, the auth client updates the stored refresh token in memory (refresh-token rotation support for the active runtime session).

### 5. MCM config fields

**Choice**: Two MCM fields for automated auth:
- `auth_client_id` — Keycloak client ID
- `auth_refresh_token` — Keycloak refresh token

**Rationale**: This is the minimum configuration that still preserves per-player identity. Token URL is derived from `service_url` host to avoid extra UI complexity.

`ws_bearer_token` is kept for backward compatibility but deprioritized in the UI — if refresh-token auth is configured, it takes precedence.

### 6. Token endpoint derivation from service URL

**Choice**: Build token endpoint in Lua from `service_url` origin:

`<origin>/auth/realms/talker/protocol/openid-connect/token`

`ws://` maps to `http://`, and `wss://` maps to `https://`.

**Rationale**: Keeps MCM at two fields while remaining deployment-aware.

### 7. Integration point: `get_service_url()` in `talker_ws_integration.script`

**Choice**: Modify `get_service_url()` to try refresh-token auth first, fall back to static `ws_bearer_token`, then no token.

```
get_service_url():
  1. If auth_client_id + auth_refresh_token configured:
     → derive token_url from service_url
     → keycloak_client.get_cached_token() or keycloak_client.fetch_token()
     → append ?token=<access_token> to URL
  2. Else if ws_bearer_token configured:
     → append ?token=<static_token> (legacy behavior)
  3. Else:
     → bare URL (local dev mode)
```

## Risks / Trade-offs

- **[Risk] Keycloak unreachable at game load** → Mitigation: 5-second timeout on token fetch. WS falls back to reconnect loop with backoff. Token fetch retried on each reconnect attempt.
- **[Risk] Refresh token in MCM plaintext** → Mitigation: same local-save security posture as existing API key fields; token values are never logged.
- **[Risk] Refresh token revocation / invalid_grant** → Mitigation: return clear fetch errors and fall back to `ws_bearer_token` when set; user can replace refresh token in MCM.
- **[Risk] pollnet HTTP blocking game thread** → Mitigation: Fetch happens only on game load and reconnect, with a hard timeout. Typical Keycloak response is <100ms.
- **[Trade-off] Derived token URL assumes `/auth/realms/talker/...`** → Intentional simplification for two-field UX; advanced deployments can still use `ws_bearer_token` fallback.
