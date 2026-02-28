## 1. Core Infrastructure — Outbox & Session Models

- [x] 1.1 Create `transport/outbox.py` with `Outbox` class (append, drain, TTL expiration, max-size FIFO eviction)
- [x] 1.2 Create `transport/session.py` with `SessionContext` dataclass (session_id, active connection, outbox ref, created_at, last_activity)
- [x] 1.3 Create `transport/session_registry.py` with `SessionRegistry` class (per-session ConfigMirror, SpeakerSelector, SessionContext management, get/create/remove)
- [x] 1.4 Add `outbox_ttl_minutes` and `outbox_max_size` to `config.py` Settings
- [x] 1.5 Write tests for `Outbox` (append, drain, TTL expiration, max-size eviction, empty drain)
- [x] 1.6 Write tests for `SessionRegistry` (get_config, get_speaker_selector, session isolation, remove_session)

## 2. WSRouter Session Awareness

- [x] 2.1 Add reverse token lookup to `parse_tokens()` — return both `name→token` and `token→name` maps
- [x] 2.2 Add `_sessions: dict[str, SessionContext]` and `_conn_to_session: dict[WebSocket, str]` to WSRouter
- [x] 2.3 Update `websocket_endpoint()` — resolve token to session_id on connect, create/reuse SessionContext, populate reverse mapping, drain outbox on reconnect
- [x] 2.4 Update `_remove_connection()` — set SessionContext.connection to None, log outbox status, keep session alive
- [x] 2.5 Add `session: str | None` parameter to `publish()` — targeted send to one session's connection or outbox; broadcast when None
- [x] 2.6 Update `_process_message()` — resolve session_id from connection via reverse lookup, pass to handler as second arg
- [x] 2.7 Update handler type alias: `MessageHandler = Callable[[dict, str], Awaitable[None]]` (payload, session_id)
- [x] 2.8 Update `shutdown()` — drain pending requests, close all sessions
- [x] 2.9 Write tests for session-aware WSRouter (connect with token → session_id, targeted publish, outbox buffering, reconnect drain, no-auth default session)

## 3. Per-Session Config

- [x] 3.1 Remove global singleton `config_mirror` — `SessionRegistry.get_config("__default__")` replaces it; `_get_mirror()` always goes through registry
- [x] 3.2 Update `handle_config_sync(payload, session_id)` — write to session-specific ConfigMirror via SessionRegistry
- [x] 3.3 Update `handle_config_update(payload, session_id)` — write to session-specific ConfigMirror via SessionRegistry
- [x] 3.4 Update `get_current_llm_client()` in `__main__.py` — accept session_id, read from session-specific ConfigMirror
- [x] 3.5 Write tests for per-session config isolation (sync to one session doesn't affect another)

## 4. Handler Signature Migration

- [x] 4.1 Update `handle_game_event(payload, session_id)` — thread session_id to DialogueGenerator calls
- [x] 4.2 Update `handle_player_dialogue(payload, session_id)` — thread session_id
- [x] 4.3 Update `handle_player_whisper(payload, session_id)` — thread session_id
- [x] 4.4 Update `handle_heartbeat(payload, session_id)` — session-scoped ack publish
- [x] 4.5 Update all existing handler tests to pass session_id as second argument

## 5. DialogueGenerator Session Threading

- [x] 5.1 Add `session_id` parameter to `generate_from_event()` and `generate_from_instruction()`
- [x] 5.2 Update `_pick_speaker()` — use `get_speakers(session_id)` which returns session-scoped SpeakerSelector from SessionRegistry when available
- [x] 5.3 Update `_generate_dialogue_for_speaker()` — pass session to `publisher.publish()` and `state.execute_batch()`
- [x] 5.4 Update `_compress_memories()` and `_update_narrative()` — pass session to publish calls
- [x] 5.5 Update LLM client access — `self.llm` property becomes `self.get_llm(session_id)` method using session-aware factory
- [x] 5.6 Write tests for DialogueGenerator with session_id (mock SessionRegistry, verify targeted publish and state query routing)

## 6. StateQueryClient Session Routing

- [x] 6.1 Add `session: str | None = None` parameter to `execute_batch()` and `_send_query()`
- [x] 6.2 Pass `session=` through to `router.publish()` calls
- [x] 6.3 Update existing StateQueryClient tests to verify session parameter forwarding

## 7. Wiring & Integration

- [x] 7.1 Update `__main__.py` lifespan — create SessionRegistry, inject into handlers and DialogueGenerator
- [x] 7.2 Update handler registration — handlers now receive (payload, session_id)
- [x] 7.3 Update health endpoint — report active sessions count
- [x] 7.4 Update debug/config endpoint — accept optional session_id query param, return session-specific or all configs
- [x] 7.5 Run full test suite — ensure all existing tests pass with session_id threading (fix any breakage)
- [x] 7.6 Write integration test: two concurrent sessions with independent config, dialogue generation, and state queries
