## 1. Lua WS Foundation

- [ ] 1.1 Audit `TALKER-fork/bin/lua/infra/HTTP/pollnet.lua` to confirm `pollnet_open_ws` FFI signature, return type of `pollnet_update`, and status query API
- [ ] 1.2 Create `bin/lua/infra/ws/client.lua` — `open(url)`, `send(handle, msg)`, `poll(handle)`, `status(handle)`, `close(handle)` wrapping pollnet WS; injectable socket factory
- [ ] 1.3 Create `bin/lua/infra/ws/codec.lua` — `encode(t, p, r)` → JSON string; `decode(raw)` → `{t, p, r, ts}` or nil+err
- [ ] 1.4 Write `tests/infra/test_ws_codec.lua` covering encode/decode round-trip, missing t field, invalid JSON
- [ ] 1.5 Write `tests/infra/test_ws_client.lua` using injected mock socket — open/send/poll/status/close scenarios

## 2. Lua Service Channel

- [ ] 2.1 Create `bin/lua/infra/service/channel.lua` — state machine (DISCONNECTED → CONNECTING → CONNECTED → RECONNECTING), `init`, `tick`, `publish`, `on`, `request`, `shutdown`, `get_status`
- [ ] 2.2 Implement outbound queue with `MAX_QUEUE_SIZE = 100`, flush-on-connect logic
- [ ] 2.3 Implement exponential backoff (1s/2s/4s/8s/cap 30s, ±20% jitter) for RECONNECTING state
- [ ] 2.4 Implement `on_reconnect` callback — fires `config.sync` publish on reconnect
- [ ] 2.5 Implement tick drain loop — call `ws_client.poll` up to `MAX_MESSAGES_PER_TICK = 20` per tick
- [ ] 2.6 Implement request/response correlation — generate UUID `r`, store future in pending table, resolve on matching `r` response
- [ ] 2.7 Write `tests/infra/test_service_channel.lua` — state machine transitions, queue flush, reconnect callback, request correlation, tick drain limit

## 3. Lua Mic Channel

- [ ] 3.1 Create `bin/lua/infra/mic/channel.lua` — thin variant of service-channel with `start_session(on_status, on_result)` and auto-cleanup on `mic.result`
- [ ] 3.2 Write `tests/infra/test_mic_channel.lua` — session registration, handler clearing, auto-cleanup after result

## 4. Python WS Router

- [ ] 4.1 Create `talker_service/src/talker_service/transport/ws_router.py` — `WSRouter` class with FastAPI `@app.websocket("/ws")` handler
- [ ] 4.2 Implement JSON envelope parse — `json.loads(raw)`, extract `t`/`p`/`r`; log and discard malformed frames
- [ ] 4.3 Implement `r`-field short-circuit — check `r` before handler dispatch; resolve `pending_requests[r]` future; log warning on unknown `r`
- [ ] 4.4 Implement `register_handler(topic, fn)` and handler dispatch via `asyncio.create_task`
- [ ] 4.5 Implement `publish(topic, payload)` — encode envelope, send to all connected clients
- [ ] 4.6 Implement `stop()` — close all active WS connections with code 1001, cancel receive loop
- [ ] 4.7 Implement `TALKER_TOKENS` parsing — `name:token,...` format, strip whitespace, skip malformed entries with warning
- [ ] 4.8 Implement token validation on WS upgrade — extract `?token=`, reject with close 4001 on mismatch; accept all when `TALKER_TOKENS` unset
- [ ] 4.9 Update `talker_service/src/talker_service/state/client.py` — replace ZMQ `pending_requests` registration with `WSRouter` injection; `execute_batch` sends via `WSRouter.publish` with `r` field; response resolved by `r`-field routing
- [ ] 4.10 Update `talker_service/src/talker_service/__main__.py` — replace `ZMQRouter` construction with `WSRouter`; register same topic handlers; remove `state.response` handler registration
- [ ] 4.11 Write `talker_service/tests/unit/test_ws_router.py` — connection acceptance, envelope parse, r-field short-circuit, handler dispatch, publish, token validation
- [ ] 4.12 Write `talker_service/tests/unit/test_service_token_auth.py` — TALKER_TOKENS parsing, valid/invalid/missing token scenarios, no-auth local mode
- [ ] 4.13 Update/port `talker_service/tests/unit/test_state_query_client.py` — mock WSRouter instead of ZMQRouter

## 5. Game Scripts

- [ ] 5.1 Create `gamedata/scripts/talker_ws_integration.script` — thin adapter: register tick timer → `service_channel.tick()` and `mic_channel.tick()`; HUD status display; `on_game_load` → `config.sync`; `on_game_unload` → `shutdown()`
- [ ] 5.2 Create `gamedata/scripts/talker_ws_command_handlers.script` — handlers for `dialogue.display`, `memory.update` via `service_channel.on(...)` (mirrors `talker_zmq_command_handlers.script` structure)
- [ ] 5.3 Create `gamedata/scripts/talker_ws_query_handlers.script` — state query handler registered via `service_channel.on("state.query.batch", ...)` that responds via `service_channel.publish("state.response", ..., r=request_r)`
- [ ] 5.4 Update `bin/lua/infra/mic/microphone.lua` — replace `zmq_bridge` require with `mic.channel` require; update `start`/`stop` to use `mic_channel.start_session` / `mic_channel.publish`
- [ ] 5.5 Update `bin/lua/app/talker.lua` (or `interface.lua`) — replace `publisher.send_game_event` call with `service_channel.publish("game.event", ...)` 
- [ ] 5.6 Update `talker_input_chatbox.script` — replace ZMQ publisher call with `service_channel.publish("player.dialogue", ...)`
- [ ] 5.7 Update `talker_input_mic.script` — replace ZMQ publisher call with `mic_channel.publish("mic.start", ...)` / `mic_channel.publish("mic.cancel", ...)`

## 6. mic_python WebSocket Server

- [ ] 6.1 Add asyncio WebSocket server in `mic_python/python/main.py` on `MIC_PORT` (default 5558) — `asyncio.start_server` with single-connection enforcement (close 4000 on second connection)
- [ ] 6.2 Route inbound WS frames by `t` field: `mic.start` → begin recording, `mic.cancel` → cancel, `tts.speak` → enqueue TTS
- [ ] 6.3 Replace ZMQ pub socket sends (`tts.started`, `tts.done`, `mic.status`, `mic.result`) with WS send to connected client using JSON envelope
- [ ] 6.4 Remove ZMQ `context.socket(zmq.SUB)` subscription logic from `main.py`
- [ ] 6.5 Add `websockets` Python package to `mic_python/python/` requirements (if applicable) or use stdlib `asyncio` streams

## 7. Documentation & API Contract

- [ ] 7.1 Create `docs/ws-api.yaml` — full OpenAPI/YAML description of JSON envelope format, all service topics (Lua→Python and Python→Lua), mic topics, state query protocol, auth query param, and close codes
- [ ] 7.2 Update `docs/Python_Service_Setup.md` — replace ZMQ port configuration with WS port; add `TALKER_TOKENS` env var setup; remove `libzmq.dll` install requirement
- [ ] 7.3 Update `README.md` — remove ZMQ references; add WS connection info and token auth setup for hosted deployments

## 8. Cleanup

- [ ] 8.1 Delete `bin/lua/infra/zmq/bridge.lua`
- [ ] 8.2 Delete `bin/lua/infra/zmq/publisher.lua`
- [ ] 8.3 Delete any remaining `bin/lua/infra/zmq/` files (sub_socket, etc.)
- [ ] 8.4 Delete `gamedata/scripts/talker_zmq_integration.script`
- [ ] 8.5 Delete `gamedata/scripts/talker_zmq_command_handlers.script`
- [ ] 8.6 Delete `gamedata/scripts/talker_zmq_query_handlers.script`
- [ ] 8.7 Remove `pyzmq` from `talker_service/requirements.txt`; add `websockets` if not already present
- [ ] 8.8 Remove `talker_service/src/talker_service/transport/router.py` (ZMQRouter) — or keep as `zmq_router.py` with deprecation comment if tests still reference it
- [ ] 8.9 Update `talker_service/tests/` — remove/port any tests importing `ZMQRouter` directly; run full test suite and fix failures
- [ ] 8.10 Run full Lua test suite and fix any failures caused by ZMQ module removal
