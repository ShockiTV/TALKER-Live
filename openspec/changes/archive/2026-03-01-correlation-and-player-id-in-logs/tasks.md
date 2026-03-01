## 1. WS Router: req_id counter and dispatch

- [x] 1.1 Add module-level `_req_counter: int = 0` to `ws_router.py`. In `_process_message`, after resolving `session_id` and before handler dispatch, increment the counter and assign `req_id`. Log `[R:{req_id}] Dispatching {topic}` at debug level.
- [x] 1.2 Update `MessageHandler` type alias from `Callable[[dict, str], Awaitable[None]]` to `Callable[[dict, str, int], Awaitable[None]]` (add `req_id: int` third arg).
- [x] 1.3 Change the dispatch call from `handler(payload, session_id)` to `handler(payload, session_id, req_id)`.

## 2. Handler signature updates

- [x] 2.1 Update all 8 handler functions to accept `req_id: int = 0` as third positional parameter:
  - `handle_game_event`, `handle_player_dialogue`, `handle_player_whisper`, `handle_heartbeat` in `events.py`
  - `handle_config_update`, `handle_config_sync` in `config.py`
  - `handle_audio_chunk`, `handle_audio_end` in `audio.py`

## 3. Log prefix helper

- [x] 3.1 Add a `_prefix(req_id, session_id=None, dialogue_id=None) -> str` helper function (in a shared location, e.g. `handlers/_log.py` or inline in generator). Returns formatted prefix string: `[R:{req_id}]`, `[R:{req_id} S:{session_id}]`, or `[R:{req_id} S:{session_id} D#{dialogue_id}]`. Omit `S:` segment when session_id is `"__default__"` or None. Omit `R:` when req_id is 0/None. Omit `D#` when dialogue_id is None.

## 4. Event handler correlation logging

- [x] 4.1 In `handle_game_event`: log the event receipt line with `[R:{req_id} S:{session}]` prefix (use helper). Pass `req_id` to `_handle_idle_event` and `_handle_regular_event`.
- [x] 4.2 In `_handle_idle_event` and `_handle_regular_event`: accept `req_id` parameter, pass it to `generate_from_instruction` / `generate_from_event` as `req_id=req_id`.
- [x] 4.3 In `handle_heartbeat`, `handle_player_dialogue`, `handle_player_whisper`: add `[R:{req_id}]` prefix to their primary log lines.

## 5. Config and audio handler correlation logging

- [x] 5.1 In `handle_config_update` and `handle_config_sync`: add `[R:{req_id} S:{session}]` prefix to the log lines.
- [x] 5.2 In `handle_audio_chunk` and `handle_audio_end`: add `[R:{req_id}]` prefix to the log lines.

## 6. Generator: thread req_id and assign dialogue_id earlier

- [x] 6.1 Add `req_id: int | None = None` parameter to `generate_from_event`, `generate_from_instruction`, `_pick_speaker`, `_generate_dialogue_for_speaker`, `_publish_dialogue`, and `_maybe_compress_memory`.
- [x] 6.2 Move `dialogue_id` assignment (the `_dialogue_counter` increment) from `_publish_dialogue` to the top of `_generate_dialogue_for_speaker`. Pass `dialogue_id` down to `_publish_dialogue`.
- [x] 6.3 Update all `logger.*` calls in the generator to use the prefix helper with `req_id`, `session_id`, and `dialogue_id` as available.

## 7. Tests

- [x] 7.1 Update existing Python tests that call handler functions directly to pass `req_id=0` (or any int) as the third argument. Search for `handle_game_event(`, `handle_config_update(`, etc. in test files.
- [x] 7.2 Update existing generator tests that call `generate_from_event` / `generate_from_instruction` to verify they accept `req_id` without error.
- [x] 7.3 Add a unit test verifying `_prefix()` helper produces correct output for all combinations (req_id only, +session, +dialogue_id, default session omitted).
- [x] 7.4 Run full Python test suite and fix any remaining failures.
