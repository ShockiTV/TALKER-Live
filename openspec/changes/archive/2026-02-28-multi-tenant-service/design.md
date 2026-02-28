## Context

The Python service (`talker_service/`) currently operates in single-tenant mode: one WebSocket connection, one global `ConfigMirror`, one `SpeakerSelector` with shared cooldowns, and handlers that receive `(payload)` without any session context. The service will be deployed on a Hetzner VPS to serve multiple concurrent players via their Bridge services, each connecting with its own invite code.

Key constraints:
- No wire protocol changes — session identity comes from the WS connection, not the envelope.
- Backward compatible — when `TALKER_TOKENS` is not configured, behavior is identical to today's single-player localhost mode.
- Python-only changes — no Lua or Bridge code in this scope.
- The service is async (FastAPI + asyncio), so session threading uses function arguments on the coroutine call stack, not thread-locals.

Current touch points that need session awareness:
- `WSRouter` — connection management, message dispatch, publish
- `ConfigMirror` — global singleton
- `SpeakerSelector` — global shared cooldowns
- Event handlers (`handle_game_event`, `handle_player_dialogue`, `handle_player_whisper`, `handle_heartbeat`) — `(payload)` signature
- `DialogueGenerator` — `generate_from_event()`, `generate_from_instruction()`
- `StateQueryClient` — `execute_batch()` publishes to all connections
- `__main__.py` — wiring, lifespan, handler registration

## Goals / Non-Goals

**Goals:**
- Every inbound WS message is associated with a `session_id` identifying the player.
- Outbound messages (dialogue.display, memory.update, state.query.batch) are routed to the correct player's connection.
- Each player has independent config (LLM provider, model, settings) and speaker cooldowns.
- When a player disconnects, outbound messages are buffered in a per-session outbox and drained on reconnect.
- When `TALKER_TOKENS` is unset, the service behaves identically to today (single default session).

**Non-Goals:**
- Correlation IDs (`cid`) — deferred to a later change.
- Suspend/resume protocol — outbox TTL is time-based only for now; explicit suspend signaling is future work.
- Bridge service changes — out of scope.
- Lua-side changes — out of scope.
- Containerization / deployment — separate VPS setup work.
- CPU service API (STT/TTS/embeddings as separate containers) — separate scope.

## Decisions

### 1. Session identity derived from token name

**Decision:** The `session_id` is the token **name** (the key in `TALKER_TOKENS=alice:tok-abc,bob:tok-xyz`). Alice's session_id is `"alice"`, Bob's is `"bob"`. When auth is disabled, a constant `"__default__"` session_id is used.

**Why:** The token name is already unique within `TALKER_TOKENS`. Using it as session_id means reconnection with the same token automatically resumes the same session — no additional handshake needed. The Bridge just reconnects with the same `?token=` parameter.

**Alternative considered:** Generate a session_id on connect and return it to the client. Rejected because it requires the Bridge to store and resend the session_id, adding protocol complexity. The token name is stable and sufficient.

### 2. WSRouter maps connections to sessions

**Decision:** `WSRouter` maintains `_sessions: dict[str, SessionContext]` where each `SessionContext` holds the active `WebSocket`, the `session_id`, and an `Outbox`. On connect, the token is resolved to a session_id and stored. On disconnect, the session persists (without a connection) so the outbox can accumulate.

**Why:** This is the single point where connection→session mapping lives. All downstream code works with `session_id` strings — only WSRouter knows about WebSocket objects.

**Alternative considered:** Middleware-based session injection (FastAPI dependency injection at the WebSocket route level). Rejected because the session lifecycle (connect/disconnect/reconnect with outbox) spans beyond a single request and needs stateful management in the router.

### 3. Handler signature changes from `(payload)` to `(payload, session_id)`

**Decision:** All registered message handlers gain a `session_id: str` parameter. `WSRouter._process_message()` resolves the session from the connection and passes it through. Handlers that need to publish back, query state, or access config use `session_id` to scope their operations.

**Why:** Explicit is better than implicit. Threading session through function arguments keeps the code testable (mock session_id in tests), avoids context variables or globals, and matches the existing async coroutine pattern.

**Alternative considered:** `contextvars.ContextVar` for session_id (set by router, read by handlers/generator). Rejected because it's implicit, harder to test, and fragile across `asyncio.create_task()` boundaries (ContextVar propagation must be carefully managed).

### 4. Per-session ConfigMirror via SessionRegistry

**Decision:** A new `SessionRegistry` class manages per-session state: `ConfigMirror`, `SpeakerSelector`, and connection tracking. `config.sync` and `config.update` handlers write to the session-specific mirror. `DialogueGenerator` reads from the session-specific mirror. The global `config_mirror` singleton has been removed; all config access goes through `SessionRegistry.get_config(session_id)` (with `\"__default__\"` for single-player mode).

**Why:** Each player may use different LLM providers, models, and prompt settings. Eliminating the global singleton ensures all code paths are session-aware and there is no accidental coupling to a stale default instance.

**Alternative considered:** Keep global `ConfigMirror` and merge all players' configs. Rejected because players have different API keys and model preferences.

### 5. Targeted publish via `session=` keyword

**Decision:** `WSRouter.publish()` gains an optional `session: str | None` parameter. When provided, the message is sent only to that session's active connection (or buffered in the session's outbox if disconnected). When `None`, it broadcasts to all connections (backward compat for service-level messages).

**Why:** State queries must go to the correct player's game. Dialogue responses must go to the correct player's Bridge. Broadcasting would send another player's dialogue to the wrong game.

### 6. Player Outbox with configurable TTL

**Decision:** Each session has an `Outbox` — a bounded, ordered list of pending messages. Messages are appended when `publish(session=...)` is called but the session has no active connection. On reconnect, the outbox is drained in order. Messages older than `outbox_ttl` (default: 30 minutes) are discarded on drain. The outbox has a max size (default: 500 messages) — oldest messages are evicted if exceeded.

**Why:** Players may pause the game, go to menus, or have network blips. Dialogue generated during disconnection should be delivered on reconnect if still fresh. The 30-minute TTL accommodates inventory management, settings tweaks, and brief network drops without accumulating stale data forever.

**Alternative considered:** Persistent outbox (Redis, SQLite). Rejected for the testing phase — in-memory is sufficient. If the service restarts, outboxes are lost, which is acceptable (the game will re-sync on reconnect).

### 7. LLM client factory keyed by session

**Decision:** The `get_current_llm_client` factory in `__main__.py` takes `session_id` and reads from the session-specific ConfigMirror. `DialogueGenerator.llm` property becomes `get_llm(session_id)` method.

**Why:** Different players may use different model methods (OpenAI vs OpenRouter) or model names. The LLM client must be resolved per-session. The existing factory function pattern is preserved, just parameterized.

### 8. Dialogue semaphore remains global, not per-session

**Decision:** The `_MAX_CONCURRENT_DIALOGUES = 3` semaphore stays global across all sessions. This limits total concurrent LLM calls, not per-player calls.

**Why:** The semaphore protects the LLM API from overcalling. With multiple players, the total load matters more than per-player load. A global semaphore of, say, 6 (tunable) ensures the VPS doesn't overwhelm the LLM API. Per-player fairness can be added later if needed.

## Risks / Trade-offs

**[Risk] Breaking existing tests** → All ~156 tests pass `(payload)` to handlers. They'll need `session_id` added. Mitigation: provide a `DEFAULT_SESSION = "__default__"` constant and update test fixtures systematically. This is mechanical but high-volume.

**[Risk] Memory growth with many sessions** → Each session holds a ConfigMirror, SpeakerSelector, and Outbox in memory. Mitigation: At testing scale (5-10 players), this is negligible. Add session cleanup (evict sessions with no connection and no outbox messages after N hours) for production readiness.

**[Risk] Outbox grows unbounded during long disconnects** → A player could disconnect for hours with the game paused. Mitigation: Max outbox size (500 messages) with FIFO eviction, plus TTL-based pruning on drain.

**[Risk] Race condition on reconnect** → If a player reconnects while the outbox is draining, messages could be sent to the old connection. Mitigation: Reconnect replaces the connection atomically in `SessionContext`. Outbox drain happens on the new connection only.

**[Risk] Single process means single point of failure** → If the Python service crashes, all players lose connection. Mitigation: Acceptable for testing phase. The Bridge auto-reconnects. The service can be restarted quickly. Future work: process supervision via Docker restart policy.

## Open Questions

- **Per-session dialogue concurrency cap?** Currently deferred — global semaphore first, revisit if one player can starve others.
- **Session eviction policy?** When to clean up a session with no connection and an empty outbox? Tentatively: 2 hours after last activity.
- **Outbox serialization format?** Messages stored as raw JSON strings (already serialized) or as dicts? Raw strings avoid re-serialization on drain.
