## Why

The `multi-tenant-service` change (archived 2026-02-28) built the infrastructure layer — `Outbox`, `SessionContext`, `SessionRegistry` — and wrote integration tests (`test_multi_session.py`), but **never wired the handler and transport layers** to use session_id. All 8 tests in `test_multi_session.py` fail because:

- `handle_config_sync` / `handle_config_update` lack a `session_id` parameter
- `handle_heartbeat` lacks a `session_id` parameter
- `DialogueGenerator.generate_from_event` / `generate_from_instruction` lack `session_id`
- `DialogueGenerator` has no `get_llm(session_id)` method
- `WSRouter.publish()` has no `session=` kwarg for targeted sends
- `StateQueryClient.execute_batch()` has no `session=` kwarg
- `WSRouter` handler dispatch is `(payload)` not `(payload, session_id)`
- Config handlers have no `set_session_registry()` function

This change completes the wiring that was left unfinished, making all `test_multi_session.py` tests pass and enabling multi-tenant operation.

## What Changes

- **Config handlers** (`handlers/config.py`): Add `_session_registry` module var, `set_session_registry()`, and `session_id` parameter to `handle_config_sync` / `handle_config_update`. When registry is set, route to per-session `ConfigMirror`.
- **Event handlers** (`handlers/events.py`): Add `session_id` parameter to `handle_heartbeat` (and other handler functions). Thread session through all `publish()` calls.
- **DialogueGenerator** (`dialogue/generator.py`): Add `session_id` parameter to `generate_from_event`, `generate_from_instruction`, and internal methods. Add `get_llm(session_id)` method replacing the `llm` property. Support factory introspection for session-aware vs zero-arg factories.
- **WSRouter** (`transport/ws_router.py`): Add `session=` kwarg to `publish()` for targeted sends (or outbox buffering). Update `MessageHandler` type to `(payload, session_id)`. Update `_process_message` to resolve and pass `session_id`.
- **StateQueryClient** (`state/client.py`): Add `session=` kwarg to `execute_batch()`, thread to `publish()`.
- **`__main__.py` wiring**: Create `SessionRegistry`, inject into handlers and generator.
- **Existing tests**: Update all handler test calls to include `session_id` (use `DEFAULT_SESSION` for backward compat).

## Capabilities

### Modified Capabilities
- `session-aware-routing`: Complete WSRouter session dispatch and targeted publish that was left stubbed.
- `per-session-config`: Wire config handlers through SessionRegistry instead of global singleton.
- `python-dialogue-generator`: Add session_id threading through generation flow.
- `python-state-query-client`: Add session routing to batch execution.
- `python-ws-router`: Handler type becomes `(payload, session_id)`, publish gains `session=`.

## Impact

- **Python service only** — no Lua or Bridge changes.
- **All existing Python tests** need handler call signatures updated to pass `session_id` (mechanical, use `DEFAULT_SESSION`).
- **8 failing tests** in `test_multi_session.py` should pass after wiring.
- **Backward compatible**: When `TALKER_TOKENS` is unset, `DEFAULT_SESSION = "__default__"` is used throughout, preserving single-player localhost behavior.
