## Why

The game client (Lua) connects to the VPS-hosted talker_service through Caddy, which validates Keycloak JWTs. Currently, the user must manually obtain an access token via browser, paste it into MCM, and the game appends it as `?token=<jwt>` on the WebSocket URL. Keycloak access tokens expire after 5 minutes, making this workflow broken for any real play session — the token expires before meaningful gameplay occurs, and there is no refresh mechanism.

The OAuth2 refresh-token flow solves this while preserving per-player identity: each player gets their own refresh token once (outside the game), then the game exchanges that refresh token for short-lived access tokens before each WebSocket connect. Caddy still validates JWTs as before, but now the JWT `sub` remains a player identity rather than a shared service account.

## What Changes

- Keep the Lua auth client module (`bin/lua/infra/auth/`) but switch it from client-credentials grant to refresh-token grant
- Change MCM auth configuration to exactly two fields: `auth_client_id` and `auth_refresh_token`
- Derive the token endpoint from `service_url` (same host, path `/auth/realms/talker/protocol/openid-connect/token`) so no token URL MCM field is needed
- Modify the WS connection lifecycle in `talker_ws_integration.script` to fetch a fresh access token before connecting (and on reconnect)
- Support refresh-token rotation when Keycloak returns a replacement refresh token in the token response
- Update Caddy config to extract JWT from `?token=` query param into the Authorization header (already done)
- Keep `ws_bearer_token` as fallback for backwards compatibility and local troubleshooting

## Capabilities

### New Capabilities
- `oauth-refresh-token`: Lua-side OAuth2 refresh-token exchange — HTTP POST to Keycloak token endpoint, parse JSON response, extract `access_token`, cache token/expiry, rotate `refresh_token` when present

### Modified Capabilities
- `service-token-auth`: Python-side token validation is unchanged, but Lua-side token acquisition shifts from static paste/client-secret flow to automated refresh-token exchange. The `?token=` query param on the WS URL remains the transport mechanism. No Python changes needed.

## Impact

- **Lua code**: New `infra/auth/` module, changes to `interface/config.lua` (new getters), `talker_ws_integration.script` (token fetch before connect)
- **MCM UI**: Provide two refresh-token auth fields (`auth_client_id`, `auth_refresh_token`) and keep `ws_bearer_token` fallback
- **Caddy**: Already updated — `request_header` injects `Authorization: Bearer` from `?token=` query param
- **Keycloak**: Requires a client that allows refresh-token exchange and provides per-player refresh tokens (admin setup, not code)
- **Python service**: No changes — existing `TALKER_TOKENS` / JWT decode / Caddy header pass-through all work as-is
- **Local dev**: Unaffected — when auth fields are empty, the existing no-auth local mode applies (no token appended to URL)
