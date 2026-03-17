## 1. Config Layer

- [x] 1.1 Replace auth defaults with two-field model in `config_defaults.lua`: `auth_client_id`, `auth_refresh_token` (default `""`)
- [x] 1.2 Update `interface/config.lua` getters to `config.auth_client_id()` and `config.auth_refresh_token()`
- [x] 1.3 Update MCM UI in `talker_mcm.script` to show only `auth_client_id` and `auth_refresh_token` for automated auth

## 2. Keycloak Auth Client

- [x] 2.1 Switch `keycloak_client.configure()` to `(token_url, client_id, refresh_token)`
- [x] 2.2 Change `fetch_token()` grant body to refresh-token flow (`grant_type=refresh_token`)
- [x] 2.3 Support refresh-token rotation when `refresh_token` appears in token response
- [x] 2.4 Ensure `refresh_token` and access token values are never logged

## 3. WS Integration

- [x] 3.1 Derive Keycloak token URL from `service_url` origin in `talker_ws_integration.script`
- [x] 3.2 Modify `get_service_url()` to try refresh-token auth first, then `ws_bearer_token`, then bare URL
- [x] 3.3 Configure/fetch tokens on reconnect using the bridge pre-connect hook

## 4. Tests

- [x] 4.1 Update `keycloak_client.lua` tests for refresh-token request body and rotation behavior
- [x] 4.2 Update config getter tests for `auth_client_id` and `auth_refresh_token`
- [x] 4.3 Update WS URL precedence tests for refresh-token auth > bearer > none
