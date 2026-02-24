## Why

The current ZMQ transport requires `libzmq.dll` (an external install) and embeds all connection lifecycle logic in `talker_zmq_integration.script`, a game callback file that cannot be unit-tested. This blocks two goals: deploying the Python service to a hosted/shared server with token-based user authentication, and making the connection lifecycle testable. WebSocket via `pollnet.dll` (already bundled) solves both: no new dependency, and the lifecycle can live in `bin/lua/` where the engine facade + mock pattern applies.

## What Changes

- **Replace ZMQ transport with WebSocket** — `pollnet_open_ws` (already in `pollnet.dll`) replaces the FFI `libzmq.dll` binding
- **New wire format: JSON envelope** — `{"t": topic, "p": payload, "r": request_id, "ts": timestamp}` replaces the fragile `"topic json_payload"` string-split pattern; `r` field enables direct request/response routing without a named handler registration
- **Two independent WS connections from Lua** — one to `talker_service` (service channel), one to `mic_python` (mic channel); each with its own reconnect state machine
- **Extract lifecycle to `bin/lua/`** — `talker_zmq_integration.script` is deleted; all logic moves to `infra/service/channel.lua` and `infra/ws/client.lua`; the replacement `talker_ws_integration.script` becomes a thin timer → `channel.tick()` adapter
- **Python: FastAPI WebSocket endpoint** — `WSRouter` replaces `ZMQRouter`; `@app.websocket("/ws")` accepts connections; incoming `r` field bypasses handler dispatch directly to `pending_requests`
- **mic_python: asyncio WS server** — drops ZMQ pub socket, adds WS server on `MIC_PORT`; same message surface (`mic.status`, `mic.result`, `tts.*`)
- **Static token auth** — `TALKER_TOKENS=name:token,...` env var; unset = no-auth local mode; invalid token closes with code 4001; token passed via `?token=xxx` query param
- **No heartbeat** — WS close frame is the disconnect signal; reconnect logic in channel state machine handles drop/resume; `on_reconnect` fires `config.sync`
- **Remove `libzmq.dll` dependency** — `bin/lua/infra/zmq/` directory deleted
- **BREAKING**: `talker_zmq_integration.script`, `talker_zmq_query_handlers.script`, `talker_zmq_command_handlers.script` deleted; replaced by `talker_ws_integration.script`, `talker_ws_query_handlers.script`, `talker_ws_command_handlers.script`
- **BREAKING**: `docs/zmq-api.yaml` superseded by `docs/ws-api.yaml`; wire format section updated

## Capabilities

### New Capabilities

- `ws-client`: Thin pollnet WebSocket connection wrapper — `open(url)`, `send(msg)`, `poll() → msg|nil`, `status()`, `close()`; injectable for tests
- `ws-codec`: JSON envelope encode/decode — `encode(t, p, r)` → string; `decode(raw)` → `{t, p, r, ts}`; validates required fields
- `service-channel`: Lua service channel — `init(url)`, `tick()`, `publish(topic, payload)`, `on(topic, fn)`, `request(topic, payload, cb)`, `shutdown()`, `get_status()`; reconnect state machine (connecting → connected → reconnecting) with exponential backoff; `on_reconnect` fires `config.sync`
- `mic-ws-channel`: Lua mic channel — thin variant of `service-channel` for mic connection; registers `mic.status` / `mic.result` handlers per session; session cleanup on `mic.result`
- `python-ws-router`: Python `WSRouter` — FastAPI `@app.websocket("/ws?token=xxx")`; JSON envelope parse; `r` field → direct `pending_requests` resolution; `publish(topic, payload)` → broadcast; token validation from `TALKER_TOKENS`
- `service-token-auth`: Static token auth — `TALKER_TOKENS` env var parsing (`name:token,...`); unset = no-auth; close 4001 on invalid token; single-tenant (Change 1)
- `ws-api-contract`: Updated API contract doc (`docs/ws-api.yaml`) — describes JSON envelope format, all topics, state query protocol over WS

### Modified Capabilities

- `script-logic-extraction`: Extended to cover `talker_zmq_integration.script` lifecycle — connection init, tick, HUD status display, and shutdown must now delegate to `infra.service.channel` rather than calling ZMQ bridge directly
- `python-state-query-client`: Transport changes — `StateQueryClient` sends `state.query.batch` and resolves via WS response (envelope `r` field) rather than ZMQ PUB/SUB round-trip; interface unchanged
- `mic-zmq-transport`: Transport changes — all ZMQ PUB/SUB ports replaced with WS; mic_python exposes an asyncio WS server; topic surface (`tts.speak`, `tts.started`, `tts.done`, `mic.status`, `mic.result`) unchanged

## Impact

- **Deleted files**: `bin/lua/infra/zmq/bridge.lua`, `bin/lua/infra/zmq/publisher.lua`, `bin/lua/infra/zmq/sub_socket.lua` (if exists); `gamedata/scripts/talker_zmq_integration.script`, `talker_zmq_query_handlers.script`, `talker_zmq_command_handlers.script`
- **New files**: `bin/lua/infra/ws/client.lua`, `bin/lua/infra/ws/codec.lua`, `bin/lua/infra/service/channel.lua`, `bin/lua/infra/mic/channel.lua`; `gamedata/scripts/talker_ws_integration.script`, `talker_ws_query_handlers.script`, `talker_ws_command_handlers.script`; `talker_service/src/talker_service/transport/ws_router.py`
- **Modified files**: `talker_service/src/talker_service/__main__.py` (swap router construction), `mic_python/python/main.py` (drop ZMQ pub, add WS server), `docs/zmq-api.yaml` → `docs/ws-api.yaml`, `requirements.txt` (remove `pyzmq`, add `websockets`)
- **Dependencies removed**: `pyzmq`, `libzmq.dll`
- **Dependencies added**: `websockets` (Python); pollnet already present (Lua)
- **Not in scope**: Multi-tenant connections, per-connection config, ConnectionContext, in-flight LLM recovery on reconnect (deferred to `multi-tenant-ws` change)
