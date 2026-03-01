## Context

The bridge (`talker_bridge/python/main.py`) has a hardcoded `SERVICE_WS_URL = "ws://127.0.0.1:5557/ws"`. For VPS deployment, this needs to be configurable. The MCM already has a "Python Service Configuration" section with `ws_host`, `mic_ws_port`, and `llm_timeout`. A `ws_token` default already exists in `config_defaults.lua` but lacks an MCM UI field.

The bridge receives all MCM values via `config.sync` on game load and reconnect, and individual changes via `config.update`. Currently it proxies these transparently to the service. The bridge can intercept these to extract the upstream URL.

The Lua game already builds its bridge connection URL from `ws_host` + `mic_ws_port` + `ws_token`. The new `service_url` field is the bridge's upstream URL — a separate concern.

## Goals / Non-Goals

**Goals:**
- Player sets `service_url` (and optionally `ws_token`) in MCM
- Bridge picks up the URL from `config.sync` on game load
- Bridge reconnects when `service_url` or `ws_token` changes mid-session via `config.update`
- Env-var `SERVICE_WS_URL` remains as fallback for bridge-only (no-game) testing
- Default points to the shared server (`wss://talker-live.duckdns.org/ws`); local users can override to `ws://127.0.0.1:5557/ws`

**Non-Goals:**
- No changes to the service-side auth or WebSocket protocol
- No runtime URL validation beyond what `websockets` enforces
- No bridge-side token refresh or rotation

## Decisions

### D1: New MCM field `service_url` (full URL)

**Decision**: Add a text-input MCM field `service_url` defaulting to `wss://talker-live.duckdns.org/ws`. Player enters the full URL including scheme and path. The `ws_token` field appends `?token=<value>` if non-empty.

**Rationale**: A single URL field is simplest. The default points to the shared community server. Players running a local service can change it to `ws://127.0.0.1:5557/ws`. No need to split into host/port/scheme.

**Alternative considered**: Separate `service_host`, `service_port`, `service_tls` fields. Rejected — more fields to configure, more assembly logic, and users already have a complete URL from their VPS setup.

### D2: Bridge intercepts config.sync/update, still proxies to service

**Decision**: The bridge peeks at `config.sync` and `config.update` messages before forwarding them to the service. If `service_url` or `ws_token` appears, the bridge updates its upstream URL and triggers a reconnect.

**Rationale**: Minimal change — the bridge already processes local topics (`mic.start`, `mic.stop`) from the Lua message stream. Adding `service_url` extraction follows the same pattern. The message is still proxied to the service (which ignores fields it doesn't need).

### D3: Reconnect uses existing retry loop

**Decision**: When the URL changes, close the current service connection. The existing `service_reader()` retry loop will reconnect to the new URL automatically within 3 seconds.

**Rationale**: No new reconnection logic needed. The `service_reader()` already handles disconnects gracefully with exponential-free 3s retry.

### D4: Env-var fallback for standalone bridge testing

**Decision**: On startup (before any `config.sync`), the bridge reads `SERVICE_WS_URL` from `os.environ` with default `wss://talker-live.duckdns.org/ws`. A `config.sync` from the game overrides this.

**Rationale**: The bridge can run without the game (for testing, debugging). The env-var gives a way to point it at a remote service without a game running.

## Risks / Trade-offs

- **[Risk] Config.sync arrives after bridge already connected** → Expected flow: bridge starts, connects to default/env URL, game connects, sends config.sync, bridge reconnects to MCM URL. The 2-second delay on initial config.sync is acceptable — just one reconnect.
- **[Risk] Player enters malformed URL** → `websockets.connect()` will raise, the retry loop logs the error every 3s. Clear enough for debugging. No need for upfront validation.
- **[Risk] Token visible in MCM text field** → MCM input fields show text in plaintext. Acceptable for a game mod — the alternative (hidden field) is not supported by MCM.
