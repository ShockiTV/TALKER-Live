## Why

The bridge's upstream service URL is hardcoded to `ws://127.0.0.1:5557/ws`. With VPS deployment, the bridge needs to connect to a remote `wss://` endpoint with token auth. All other player-facing config lives in MCM — the service URL should too, so the bridge picks it up from `config.sync` without manual file editing.

## What Changes

- Add `service_url` and `ws_token` MCM input fields in the Python Service section
- Include `service_url` in the `config.sync` payload sent to the bridge
- Bridge intercepts `config.sync` (and `config.update` for `service_url` / `ws_token`) to build the upstream URL
- Bridge reconnects to the new URL when it changes
- Fallback: bridge uses env-var `SERVICE_WS_URL` if no `config.sync` arrives (standalone mode)

## Capabilities

### New Capabilities

- `bridge-remote-config`: Bridge reads upstream service URL from MCM config (via `config.sync`), falling back to env-var, supporting both local `ws://` and remote `wss://` with token auth

### Modified Capabilities

- `talker-mcm`: Add `service_url` and `ws_token` input fields to the Python Service configuration section

## Impact

- `gamedata/scripts/talker_mcm.script` — new MCM fields: `service_url`, `ws_token`
- `bin/lua/interface/config.lua` — getter for `service_url`, include in `get_all_config()`
- `bin/lua/interface/config_defaults.lua` — default for `service_url`
- `talker_bridge/python/main.py` — intercept config.sync/update, reconnect logic
- `talker_bridge/python/.env.example` — document env-var fallback
- No changes to talker_service or wire protocol
