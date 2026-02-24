## Context

The Python service currently communicates with the Lua game client via ZeroMQ (libzmq.dll FFI binding). The complete lifecycle — connection init, polling, reconnect, shutdown — lives in `gamedata/scripts/talker_zmq_integration.script`, which calls `CreateTimeEvent`, `ResetTimeEvent`, and other game globals that have no test equivalent. The mic subsystem uses a separate ZMQ SUB socket in `bin/lua/infra/zmq/bridge.lua`. The result is 637 lines of untestable, game-coupled FFI code.

The deployment constraint is that `libzmq.dll` must be installed separately by end-users for online deployment. It is not bundled with Anomaly; users hosting the service online cannot easily share a socket with remote players who have heterogeneous installs.

`pollnet.dll` ships with TALKER and is already used by the HTTP layer. It exposes `pollnet_open_ws(url)` — a WebSocket client — which removes the external dependency and enables the engine-facade + mock pattern for the transport layer.

## Goals / Non-Goals

**Goals:**
- Replace ZMQ transport with WebSocket using `pollnet.dll` (already bundled)
- Extract connection lifecycle from `talker_zmq_integration.script` into `bin/lua/infra/` (testable via mock socket injection)
- Enable hosted deployment with static token authentication (`TALKER_TOKENS` env var)
- Replace fragile `"topic json"` string-split wire format with a typed JSON envelope
- Remove `libzmq.dll` and `pyzmq` dependencies

**Non-Goals:**
- Multi-tenant connections (deferred to `multi-tenant-ws` change)
- Per-connection MCM config scoping
- In-flight LLM request recovery on reconnect
- TLS/certificate pinning (operator concern — standard HTTPS proxying is sufficient)

## Decisions

### Decision 1: WebSocket over HTTP long-polling or raw TCP

**Chosen**: WebSocket via `pollnet_open_ws`

**Rationale**: `pollnet_open_ws` is already in the DLL, zero new runtime installs. WS gives a persistent bidirectional channel with standard close frames as disconnect signal, matching the existing PUB/SUB topology. HTTP long-polling would require matching request IDs on both ends and would complicate the state-query round-trip. Raw TCP would require a new pollnet binding.

**Alternatives considered**: HTTP polling (rejected — latency, complexity), raw TCP (rejected — no existing binding), WebRTC (rejected — wildly disproportionate).

### Decision 2: Wire format `{t, p, r, ts}` JSON envelope

**Chosen**: `{"t": "topic", "p": {...}, "r": "request-id-optional", "ts": 1234567}`

**Rationale**: Current `"topic json_payload"` format requires string-split on first space, fragile when topics contain spaces, and the dual-path `data.get("payload", data)` fallback in the Python handler is error-prone. A keyed envelope is self-describing, validated by Pydantic, and the `r` field enables direct request/response short-circuit without a named handler registration. Keys are kept short (1-2 chars) to minimise per-message overhead.

**Alternatives considered**: MessagePack (binary — harder to debug, no built-in Lua support), separate channels per direction (unnecessary complexity), keeping `"topic json"` (rejected — ambiguous, untestable codec).

### Decision 3: Single connection, two topics per channel

**Chosen**: Two independent WS connections from Lua (service channel on `WS_PORT`, mic channel on `MIC_PORT`). Each is managed by its own state machine module.

**Rationale**: Service and mic channels have divergent lifecycles (mic may be absent), divergent reconnect semantics, and different message surfaces. Multiplexing over one socket adds complexity with no benefit. Two connections keep the modules independent and testable in isolation.

**Alternatives considered**: Single muxed connection (rejected — lifecycle coupling), ZMQ-style separate SUB/PUB ports over WS (rejected — unnecessary with full-duplex WS).

### Decision 4: Auth via `?token=xxx` query param, `TALKER_TOKENS` env var

**Chosen**: Token passed as WS upgrade query parameter. Server reads `TALKER_TOKENS=name:token,...`; unset = no-auth local mode; invalid token = WS close 4001.

**Rationale**: WS upgrade happens before the application protocol starts, making query-param auth the simplest approach that requires no custom header support in `pollnet_open_ws`. Static tokens are sufficient for Change 1 (single shared user per service instance); per-user scoping is deferred to `multi-tenant-ws`. Unset = local mode preserves zero-config local experience.

**Alternatives considered**: JWT (overkill for Phase 1), Basic Auth header (pollnet may not support custom headers), no auth (rejected for online deployment goal).

### Decision 5: No heartbeat — WS close frame is disconnect signal

**Chosen**: Remove heartbeat entirely. WS protocol-level ping/pong (if enabled) is sufficient. Application-level heartbeat (`system.heartbeat` topic) deleted.

**Rationale**: The heartbeat existed to detect dead ZMQ connections which had no close notification. WS has explicit close frames. During menu pause, `pollnet_update` stops being called — pong never fires — so the server eventually drops the connection via close frame. The reconnect state machine in `service-channel` handles this. Adding an application heartbeat on top of WS ping/pong is redundant.

**Alternatives considered**: Keep heartbeat (rejected — redundant), WS server-side ping with keepalive (possible via `websockets` lib ping_interval — disabled for now to avoid confusion with game-pause drops).

### Decision 6: Reconnect via state machine with backoff, `on_reconnect` resends `config.sync`

**Chosen**: `service-channel` implements states: `DISCONNECTED → CONNECTING → CONNECTED → RECONNECTING → CONNECTING`. Exponential backoff with jitter (1s, 2s, 4s, cap 30s). On successful reconnect, `on_reconnect` fires `config.sync`.

**Rationale**: Game menu pauses the time event loop, so the channel loses its heartbeat/tick and the WS connection will drop. Without automatic reconnect, users who alt-tab or use the in-game menu lose the service permanently. `config.sync` on reconnect ensures Python has current MCM settings after the drop.

### Decision 7: Tick-driven polling, drain up to MAX_MESSAGES_PER_TICK

**Chosen**: `channel.tick()` is called by a game timer (1–5ms interval). Each tick drains up to `MAX_MESSAGES_PER_TICK = 20` frames from `pollnet_update()` to avoid blocking the game loop.

**Rationale**: Pollnet is poll-driven, not push-driven. `pollnet_update()` must be called to receive frames. The tick limit prevents the game loop from stalling if a burst of messages arrives.

### Decision 8: State query `r` field short-circuits handler dispatch

**Chosen**: `WSRouter._process_message` checks `data.get("r")` first; if set, it resolves the corresponding `pending_requests[r]` future and returns without calling any registered handler.

**Rationale**: State query responses are currently dispatched via a named `state.response` handler that must be registered at startup. The `r` field makes routing explicit and removes the handler registration. It also prevents accidentally dispatching a state response to an application handler.

## Risks / Trade-offs

| Risk | Mitigation |
|------|-----------|
| Menu pause drops WS connection (pong not processed) | Accepted — reconnect state machine handles it; `config.sync` is resent on reconnect |
| `pollnet_open_ws` has no custom header support | Use query-param auth (`?token=xxx`) instead |
| Burst messages on reconnect before Python is ready | Lua queues outbound messages during CONNECTING state; drops if queue exceeds MAX_QUEUE |
| Python `websockets` library breaking change | Pin version in `requirements.txt` |
| Existing tests assume ZMQ interface | Port ZMQ router tests to WSRouter; mock WS socket in unit tests |

## Migration Plan

1. **Parallel implementation**: Add `infra/ws/` and `infra/service/channel.lua` alongside existing `infra/zmq/` — no game files touched yet
2. **Script swap**: Replace `talker_zmq_integration.script` with `talker_ws_integration.script`; replace `talker_zmq_command_handlers.script → talker_ws_command_handlers.script`; replace `talker_zmq_query_handlers.script → talker_ws_query_handlers.script`
3. **Python swap**: Replace `ZMQRouter` with `WSRouter` in `__main__.py`; update `StateQueryClient` to use WS response routing
4. **mic_python**: Drop ZMQ pub socket; add asyncio WS server
5. **Delete ZMQ artifacts**: Remove `bin/lua/infra/zmq/`, `libzmq.dll` reference from setup docs
6. **Rollback**: Revert script files and `__main__.py`; ZMQ artifacts are deleted last so can be restored from git

**No database migrations** — wire format change is transparent to the persistence layer (memory store, event store).

## Open Questions

- Should `pollnet_open_ws` reconnect use the same socket handle or create a new one? (Likely new handle — closing and re-opening is safer)
- What is the correct `pollnet_update()` return type on receive — string or nil on empty? (Need to verify from `TALKER-fork/bin/lua/infra/HTTP/pollnet.lua` FFI bindings before implementing)
- Should `MIC_PORT` be configurable via MCM or fixed default (default 5558)?
