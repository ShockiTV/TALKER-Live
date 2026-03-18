## 1. Config Layer

- [x] 1.1 Replace auth defaults in `config_defaults.lua`: remove `auth_refresh_token`, add `auth_username` and `auth_password` (default `""`)
- [x] 1.2 Update `interface/config.lua` getters: remove `auth_refresh_token()` and `auth_client_secret()`, add `auth_username()` and `auth_password()`; update `get_all_config()`
- [x] 1.3 Update MCM UI in `talker_mcm.script`: replace `auth_client_secret` and `auth_refresh_token` fields with `auth_username` and `auth_password`; update defaults table
- [x] 1.4 Update MCM XML strings (eng + rus): replace client_secret/refresh_token entries with username/password entries

## 2. Keycloak Auth Client

- [x] 2.1 Switch `keycloak_client.configure()` signature to `(token_url, client_id, username, password)`
- [x] 2.2 Change `build_form_body()` to ROPC grant (`grant_type=password` with `username` + `password`); remove refresh-token rotation
- [x] 2.3 Ensure password and access token values are never logged

## 3. WS Integration

- [x] 3.1 Replace refresh-token resolution logic (truncation detection, file fallback) with simple ROPC config check in `talker_ws_integration.script`
- [x] 3.2 Update `get_auth_config_values()` / `is_ropc_auth_configured()` / `configure_keycloak_client()` for username+password
- [x] 3.3 Update `get_service_url()` to try ROPC auth first, then `ws_bearer_token`, then bare URL

## 4. Tests

- [x] 4.1 Update `keycloak_client.lua` tests for ROPC request body (`grant_type=password`), remove rotation test
- [x] 4.2 Update config getter tests for `auth_username` and `auth_password`
