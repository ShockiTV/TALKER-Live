## Why

The game client (Lua) connects to the VPS-hosted talker_service through Caddy, which validates Keycloak JWTs. Currently, the user must manually obtain an access token via browser, paste it into MCM, and the game appends it as `?token=<jwt>` on the WebSocket URL. Keycloak access tokens expire after 5 minutes, making this workflow broken for any real play session — the token expires before meaningful gameplay occurs, and there is no refresh mechanism.

The OAuth2 Resource Owner Password Credentials (ROPC) flow solves this while preserving per-player identity: users enter their Keycloak username and password in MCM (both short strings that fit within MCM's ~254 char limit), and the game exchanges these for short-lived access tokens before each WebSocket connect. Caddy still validates JWTs as before, and the JWT `sub` remains the player's Keycloak user ID.

## What Changes

- Keep the Lua auth client module (`bin/lua/infra/auth/`) but switch it from client-credentials grant to ROPC grant (`grant_type=password`)
- Change MCM auth configuration to three fields: `auth_client_id`, `auth_username`, and `auth_password` — all short strings that fit in MCM
- Derive the token endpoint from `service_url` (same host, path `/auth/realms/talker/protocol/openid-connect/token`) so no token URL MCM field is needed
- Modify the WS connection lifecycle in `talker_ws_integration.script` to fetch a fresh access token before connecting (and on reconnect)
- Remove refresh-token resolution logic (file fallback, truncation detection) — no longer needed since credentials are short
- Update Caddy config to extract JWT from `?token=` query param into the Authorization header (already done)
- Keep `ws_bearer_token` as fallback for backwards compatibility and local troubleshooting

## Capabilities

### New Capabilities
- `oauth-ropc`: Lua-side OAuth2 ROPC exchange — HTTP POST to Keycloak token endpoint with `grant_type=password`, parse JSON response, extract `access_token`, cache token/expiry

### Modified Capabilities
- `service-token-auth`: Python-side token validation is unchanged, but Lua-side token acquisition shifts from static paste/client-secret flow to automated ROPC exchange. The `?token=` query param on the WS URL remains the transport mechanism. No Python changes needed.

## Impact

- **Lua code**: New `infra/auth/` module, changes to `interface/config.lua` (new getters), `talker_ws_integration.script` (token fetch before connect)
- **MCM UI**: Provide three ROPC auth fields (`auth_client_id`, `auth_username`, `auth_password`) and keep `ws_bearer_token` fallback
- **Caddy**: Already updated — `request_header` injects `Authorization: Bearer` from `?token=` query param
- **Keycloak**: Requires "Direct Access Grants" enabled on the client (one checkbox in admin console)
- **Python service**: No changes — existing `TALKER_TOKENS` / JWT decode / Caddy header pass-through all work as-is
- **Local dev**: Unaffected — when auth fields are empty, the existing no-auth local mode applies (no token appended to URL)
