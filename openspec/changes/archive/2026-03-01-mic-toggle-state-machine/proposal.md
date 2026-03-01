## Why

Pressing the mic capture key during an active transcription caused race conditions — stale audio from a previous session could contaminate the new one, callbacks got mis-paired, and the HUD showed incorrect status. The toggle behaviour users expect (press to start, press again to stop, press again to start new while old transcribes) was not supported.

## What Changes

- **Bridge AudioStreamer rewritten** with monotonic `session_id`, explicit `start()`/`stop()`/`cancel()` methods, and `_stopped`/`_cancelled` flags that distinguish manual stop from VAD silence detection
- **Bridge publishes `mic.stopped`** to Lua when VAD auto-stops capture, so Lua can transition state without a key press
- **`mic.cancel` topic removed** from bridge `LOCAL_TOPICS` — cancel is internal-only (shutdown cleanup)
- **Service audio handlers track `_active_session_id`** — stale chunks/end signals from superseded sessions are discarded
- **`microphone.lua` rewritten** as thin hardware wrapper: `start_capture()`, `stop_capture()`, `is_recording()`, `on_stopped()`
- **`recorder.lua` rewritten** as toggle state machine with three states (idle → capturing → transcribing) using permanent `bridge_channel.on()` handlers instead of session-scoped `start_session()`
- **HUD priority**: "RECORDING" status suppresses background `mic.status` updates during active capture
- **"LISTENING" renamed to "RECORDING"** across all components
- **`talker_input_mic.script`** calls `recorder.toggle()` instead of `recorder.start()`

## Capabilities

### New Capabilities
- `mic-toggle-state-machine`: Lua-side toggle state machine (recorder.lua) that orchestrates mic capture sessions — handles overlapping capture+transcription, VAD auto-stop transitions, HUD priority, and callback delivery

### Modified Capabilities
- `mic-audio-streaming`: Bridge AudioStreamer now uses session_id tracking, publishes `mic.stopped` on VAD, `LOCAL_TOPICS` changed from `{mic.start, mic.cancel}` to `{mic.start, mic.stop}`
- `mic-ws-channel`: Mic recording no longer uses session-scoped `start_session()` — recorder registers permanent `on()` handlers instead; `mic.stopped` is a new downstream topic
- `service-whisper-transcription`: Service audio handlers now track `_active_session_id` to reject stale audio; `mic.result` and `mic.status` include `session_id` in payload

## Impact

- **Lua**: `bin/lua/infra/mic/microphone.lua`, `bin/lua/interface/recorder.lua`, `gamedata/scripts/talker_input_mic.script`
- **Python bridge**: `talker_bridge/python/main.py` (AudioStreamer)
- **Python service**: `talker_service/src/talker_service/handlers/audio.py`
- **WS API**: New `mic.stopped` topic (bridge → Lua); `mic.cancel` topic removed; `session_id` added to `mic.audio.chunk`, `mic.audio.end`, `mic.result`, `mic.status` payloads
- **Tests**: `tests/infra/mic/test_mic.lua` (14 tests), `tests/interface/test_recorder.lua` (19 tests), `tests/triggers/test_talker_trigger_mic.lua` (updated mocks)
