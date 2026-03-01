## 1. WSRouter Foundation

- [x] 1.1 Update `MessageHandler` type alias to `Callable[[dict[str, Any], str], Awaitable[None]]`
- [x] 1.2 Add `_conn_to_session: dict[WebSocket, str]` reverse lookup to WSRouter
- [x] 1.3 Update `websocket_endpoint()` to resolve session_id from token (or DEFAULT_SESSION) and maintain `_conn_to_session` map alongside `_connections`
- [x] 1.4 Update `_process_message()` to look up session_id from connection and call `handler(payload, session_id)`
- [x] 1.5 Add `session: str | None = None` kwarg to `publish()` — when provided, send only to the session's connection; when None, broadcast to all

## 2. WSRouter Outbox Fallback

- [x] 2.1 In `publish()`, when `session` is provided but the session's connection is missing, buffer the message in the session's outbox via `SessionRegistry`

## 3. Config Handler Wiring

- [x] 3.1 Add `_session_registry` module var and `set_session_registry(registry)` function to `handlers/config.py`
- [x] 3.2 Update `handle_config_sync(payload, session_id=DEFAULT_SESSION)` to route through registry when set, fall back to global singleton when not
- [x] 3.3 Update `handle_config_update(payload, session_id=DEFAULT_SESSION)` to route through registry when set, fall back to global singleton when not

## 4. Event Handler Wiring

- [x] 4.1 Update `handle_heartbeat(payload, session_id=DEFAULT_SESSION)` to publish heartbeat ack and config request with `session=session_id`
- [x] 4.2 Update `handle_game_event(payload, session_id=DEFAULT_SESSION)` to pass session_id to dialogue generator
- [x] 4.3 Update `handle_player_dialogue(payload, session_id=DEFAULT_SESSION)` and `handle_player_whisper(payload, session_id=DEFAULT_SESSION)` to pass session_id to dialogue generator

## 5. State Query Client

- [x] 5.1 Add `session: str | None = None` kwarg to `execute_batch()` and forward it to `router.publish(..., session=session)`

## 6. Dialogue Generator

- [x] 6.1 Add `get_llm(session_id=None)` method with `inspect.signature` factory introspection; retain `llm` property delegating to `get_llm(None)`
- [x] 6.2 Add `session_id: str | None = None` kwarg to `generate_from_event()` and `generate_from_instruction()`
- [x] 6.3 Thread `session_id` through all internal methods: `_pick_speaker`, `_generate_dialogue_for_speaker`, `_compress_memories`, `_update_narrative`
- [x] 6.4 Pass `session=session_id` to all `execute_batch()` and `publish()` calls within the generator

## 7. App Wiring

- [x] 7.1 Update handler registration in `__main__.py` to call `set_session_registry(registry)` on the config handler module
- [x] 7.2 Update handler registration in `__main__.py` to pass `SessionRegistry` to event handlers if needed

## 8. Test Verification

- [x] 8.1 Verify all 8 `test_multi_session.py` tests pass
- [x] 8.2 Verify all ~606 existing tests still pass (no regressions from default parameter changes)
