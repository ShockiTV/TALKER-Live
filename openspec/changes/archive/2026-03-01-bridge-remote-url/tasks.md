## 1. MCM & Lua config

- [x] 1.1 Add `service_url` and `ws_token` input fields to `talker_mcm.script` in the Python Service section
- [x] 1.2 Add `service_url` default (`wss://talker-live.duckdns.org/ws`) to `config_defaults.lua` (ws_token default already exists)
- [x] 1.3 Add `config.service_url()` getter in `interface/config.lua`
- [x] 1.4 Include `service_url` and `ws_token` in `get_all_config()` return table

## 2. Bridge: intercept config and reconnect

- [x] 2.1 Replace hardcoded `SERVICE_WS_URL` with `os.environ.get("SERVICE_WS_URL", "wss://talker-live.duckdns.org/ws")`
- [x] 2.2 Intercept `config.sync` in `lua_ws_handler` — extract `service_url` and `ws_token`, build upstream URL, trigger reconnect if changed
- [x] 2.3 Intercept `config.update` for `service_url` / `ws_token` keys — same reconnect logic
- [x] 2.4 Add `mask_token(url)` helper for safe logging; log resolved URL at startup and on change
- [x] 2.5 Reconnect mechanism: set new URL, close current `_service_ws` — existing `service_reader()` retry loop reconnects automatically

## 3. Documentation

- [x] 3.1 Create `talker_bridge/python/.env.example` documenting `SERVICE_WS_URL` env-var fallback
- [x] 3.2 Add MCM field descriptions to UI strings XML (service URL + token labels/descriptions)
