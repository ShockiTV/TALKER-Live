## 1. Bridge AudioStreamer (Python)

- [x] 1.1 Add monotonic `session_id` counter to AudioStreamer
- [x] 1.2 Include `session_id` in `mic.audio.chunk` and `mic.audio.end` payloads
- [x] 1.3 Add `_stopped` and `_cancelled` flags to distinguish stop reasons
- [x] 1.4 Implement `start()` with supersede detection (old capture loop detects new session)
- [x] 1.5 Implement `stop()` — sets `_stopped = True`, clears `_recording`
- [x] 1.6 Implement `cancel()` — sets `_cancelled = True`, clears `_recording` (shutdown only)
- [x] 1.7 Publish `mic.stopped` to Lua when VAD auto-stops (not on manual stop)
- [x] 1.8 Suppress `mic.audio.end` for superseded/cancelled sessions
- [x] 1.9 Remove `mic.cancel` from `LOCAL_TOPICS` — change to `{mic.start, mic.stop}`

## 2. Service Audio Handlers (Python)

- [x] 2.1 Add `_active_session_id` tracking to audio chunk handler
- [x] 2.2 Discard old buffer when new `session_id` arrives in `mic.audio.chunk`
- [x] 2.3 Ignore stale `mic.audio.end` where `session_id != _active_session_id`
- [x] 2.4 Include `session_id` in `mic.result` and `mic.status` payloads

## 3. Lua Microphone Wrapper

- [x] 3.1 Rewrite `microphone.lua` as thin hardware wrapper: `start_capture()`, `stop_capture()`, `is_recording()`
- [x] 3.2 Add `on_stopped()` method — resets `_recording` flag without publishing
- [x] 3.3 Remove session management and cancel functionality from microphone
- [x] 3.4 Write 14 tests in `tests/infra/mic/test_mic.lua`

## 4. Lua Recorder State Machine

- [x] 4.1 Implement three-state machine: idle → capturing → transcribing
- [x] 4.2 Implement `toggle(callback)` with state-dependent transitions
- [x] 4.3 Register permanent `bridge_channel.on()` handlers for `mic.status`, `mic.stopped`, `mic.result`
- [x] 4.4 Implement HUD priority — suppress `mic.status` during `capturing` state
- [x] 4.5 Implement `mic.stopped` handler — transition capturing → transcribing on VAD
- [x] 4.6 Implement `mic.result` handler — deliver callback, transition to idle
- [x] 4.7 Implement `_reset()` for test isolation (replaces deleted `cancel()`)
- [x] 4.8 Rename "LISTENING" to "RECORDING" across all HUD messages
- [x] 4.9 Write 19 tests in `tests/interface/test_recorder.lua` (including VAD scenarios)

## 5. Game Script Integration

- [x] 5.1 Update `talker_input_mic.script` to call `recorder.toggle()` instead of `recorder.start()`
- [x] 5.2 Update `tests/triggers/test_talker_trigger_mic.lua` to use `toggle` mock

## 6. Dead Code Removal

- [x] 6.1 Remove `recorder.cancel()` from recorder.lua
- [x] 6.2 Remove `mic.cancel_capture()` from microphone.lua
- [x] 6.3 Remove `mic.cancel` from bridge `LOCAL_TOPICS`
