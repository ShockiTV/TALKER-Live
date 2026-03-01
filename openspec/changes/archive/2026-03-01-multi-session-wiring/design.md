## Context

The `multi-tenant-service` change (archived 2026-02-28) built the infrastructure layer — `transport/outbox.py` (Outbox), `transport/session.py` (SessionContext, DEFAULT_SESSION), and `transport/session_registry.py` (SessionRegistry) — along with passing tests for those components (`test_outbox.py`, `test_session_registry.py`).

However, the handler and transport layers were never updated to use session_id. All handler functions currently accept `(payload)` only. WSRouter dispatches `handler(payload)` without session context. `publish()` broadcasts to all connections with no targeting. `DialogueGenerator` has no session threading. The result: 8 integration tests in `test_multi_session.py` fail because they exercise the expected wiring that doesn't exist.

Current state of each touch point:
- `handlers/config.py`: Global `config_mirror = ConfigMirror()` singleton. `handle_config_sync(payload)` and `handle_config_update(payload)` — single arg.
- `handlers/events.py`: `handle_heartbeat(payload)`, `handle_game_event(payload)`, `handle_player_dialogue(payload)`, `handle_player_whisper(payload)` — single arg. Heartbeat references global `config_mirror` directly.
- `dialogue/generator.py`: `generate_from_event(event, is_important=False)`, `generate_from_instruction(speaker_id, event)` — no session_id. `llm` is a `@property` (zero-arg). All internal methods (`_generate_dialogue_for_speaker`, `_compress_memories`, `_update_narrative`, `_pick_speaker`) broadcast state queries and publishes.
- `transport/ws_router.py`: `MessageHandler = Callable[[dict], Awaitable[None]]`. `_process_message` dispatches `handler(payload)`. `publish()` broadcasts to all `_connections`. No connection→session mapping.
- `state/client.py`: `execute_batch(batch, *, timeout=None)` — no session kwarg. Calls `router.publish(...)` without session.
- `__main__.py`: Creates global `config_mirror` import, wires single-arg handlers.

Constraints:
- Python-only changes — no Lua or Bridge code in scope.
- Backward compatible — when `TALKER_TOKENS` is unset, `DEFAULT_SESSION` is used. Single-player localhost is unaffected.
- ~600 existing passing Python tests (excluding the 8 failing) must continue to pass. Handlers called in existing tests receive `DEFAULT_SESSION` via default parameter.
- Session threading uses explicit function arguments, not `contextvars`.

## Goals / Non-Goals

**Goals:**
- Wire `session_id` through the entire handler → generator → state/publish call chain.
- Replace global `config_mirror` singleton with `SessionRegistry.get_config(session_id)` routing.
- Add `session=` targeted publish to WSRouter so responses go to the correct player.
- Make all 8 `test_multi_session.py` tests pass.
- Keep all ~600 existing tests passing by using default parameter values.

**Non-Goals:**
- New infrastructure classes — Outbox, SessionContext, SessionRegistry already exist and are tested.
- Correlation ID (`cid`) system — deferred.
- Outbox drain on reconnect — defer to future WSRouter work (SessionContext + Outbox exist, but drain wiring is out of scope for this change).
- Bridge or Lua changes — entirely out of scope.
- New specs or capabilities — this change modifies existing specs only.

## Decisions

### 1. Handler signature: `(payload, session_id=DEFAULT_SESSION)`

**Decision:** Add `session_id: str = DEFAULT_SESSION` as the second parameter to all handler functions. The default value preserves backward compatibility — existing callers (including ~600 tests) that pass only `payload` get `"__default__"` automatically.

**Why:** Minimal disruption. Only the WSRouter dispatch and `test_multi_session.py` pass explicit session_id. All other tests and callers work unchanged.

**Alternative considered:** Update every single test call site to include `DEFAULT_SESSION`. Rejected — high-volume mechanical churn with no benefit when the default parameter achieves the same result.

### 2. WSRouter: connection→session reverse lookup

**Decision:** Add `_conn_to_session: dict[WebSocket, str]` to WSRouter. In `websocket_endpoint()`, resolve session_id from token (or `DEFAULT_SESSION`) and store both forward (session→connection via SessionRegistry) and reverse mappings. In `_process_message`, look up session_id from the connection and pass it through to handlers.

**Why:** O(1) lookup for every inbound message. The reverse map is maintained alongside connection add/remove, which already exists.

### 3. Targeted publish: `session=` on `WSRouter.publish()`

**Decision:** Add `session: str | None = None` kwarg to `publish()`. When provided, send only to the connection for that session (or buffer in outbox if disconnected). When `None`, broadcast (current behavior). The outbox buffering is implemented via `SessionRegistry.get_session(session).outbox.append()`.

**Why:** State queries must reach the correct player's game. Dialogue responses must reach the correct player's bridge. Broadcasting would leak data between players.

### 4. DialogueGenerator: `session_id` threading

**Decision:** Add `session_id: str | None = None` kwarg to `generate_from_event()`, `generate_from_instruction()`, and all internal methods. Add `get_llm(session_id)` method replacing the `llm` property (property retained for backward-compat, delegates to `get_llm(None)`). The factory inspection uses `inspect.signature` to check if it accepts `session_id`.

**Why:** The generator is the central orchestrator that calls state queries and publishes responses. Threading session through it routes both directions correctly.

### 5. Config handler routing via optional registry

**Decision:** Add `_session_registry: SessionRegistry | None = None` module var and `set_session_registry(registry)` function to `handlers/config.py`. When registry is set, `handle_config_sync(payload, session_id)` writes to `registry.get_config(session_id)`. When `None`, falls back to global `config_mirror` (backward compat for tests that don't set up a registry).

**Why:** Gradual migration. The global singleton continues working in single-player mode and in tests that don't exercise multi-session. Only `test_multi_session.py` and `__main__.py` call `set_session_registry()`.

### 6. Dialogue concurrency semaphore remains global

**Decision:** The `_MAX_CONCURRENT_DIALOGUES` semaphore stays global. No per-session fairness mechanism.

**Why:** Protects the LLM API from total overload. Per-player fairness is a future concern for real VPS deployment.

## Risks / Trade-offs

**[Risk] Breaking existing tests via handler signature change** → Mitigated by `session_id=DEFAULT_SESSION` default. Zero existing test changes required for handler calls.

**[Risk] Missing session_id in deep call chain** → If any internal method forgets to forward `session_id`, state queries or publishes may broadcast instead of targeting. Mitigated by `test_multi_session.py` which verifies end-to-end session threading.

**[Risk] Property→method migration for `self.llm`** → Internal code that reads `self.llm` will continue to work (property delegates to `get_llm(None)`). Only session-aware call sites use `get_llm(session_id)`.

**[Risk] Outbox accumulation without drain** → Outbox is wired for append but reconnect drain is deferred. Messages may queue indefinitely. Acceptable for this change since drain can be wired separately.
