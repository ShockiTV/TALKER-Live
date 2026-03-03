# mic-audio-streaming (delta)

## MODIFIED Requirements

### Requirement: Audio capture without transcription
The Lua layer (via `talker_audio.dll` FFI) SHALL capture audio from the user's microphone without attempting to transcribe it locally. Capture is initiated by `ta_start()` and runs on the DLL's internal PortAudio thread.

#### Scenario: Capturing audio
- **WHEN** the user presses the push-to-talk hotkey (triggering `ta_start()`)
- **THEN** the DLL begins recording audio from the selected (or default) microphone device
- **AND** Lua assigns a new monotonic `session_id` to the capture session

### Requirement: Local Voice Activity Detection (VAD)
The native DLL SHALL perform local silence detection using energy-based VAD to determine when the user has stopped speaking. VAD runs inside the DLL's capture thread.

#### Scenario: Detecting end of speech
- **WHEN** audio capture is active
- **AND** the VAD detects sustained silence (configurable, default 2 seconds)
- **THEN** the DLL auto-stops capture
- **AND** `ta_poll()` returns `-1` after all buffered frames are drained

### Requirement: Audio streaming to service
Lua SHALL stream Opus-encoded audio chunks to `talker_service` over the existing pollnet WebSocket connection. Chunks are retrieved from the DLL via `ta_poll()` on each game tick.

#### Scenario: Streaming audio chunks
- **WHEN** `ta_poll()` returns a positive value (Opus frame ready)
- **THEN** Lua base64-encodes the frame and sends a `mic.audio.chunk` message with `format: "opus"` to `talker_service` via the existing WS connection

#### Scenario: End of audio stream
- **WHEN** `ta_poll()` returns `-1` (VAD auto-stop) or `-2` (manual stop)
- **AND** all buffered frames have been drained
- **THEN** Lua sends a `mic.audio.end` message to `talker_service`

### Requirement: Session ID tracking
Lua SHALL assign a monotonic integer `session_id` to each capture session. The `session_id` SHALL be included in all `mic.audio.chunk` and `mic.audio.end` messages sent to the service.

#### Scenario: Session ID increments on each start
- **WHEN** `ta_start()` is called via `microphone.start_capture()`
- **THEN** the Lua-side `session_id` increments by 1
- **AND** all subsequent `mic.audio.chunk` messages include the new `session_id`

### Requirement: Publish mic.stopped on VAD auto-stop
When `ta_poll()` returns `-1` (VAD silence detected), the Lua audio tick loop SHALL treat this as a `mic.stopped` event. No bridge message is involved — the signal comes directly from the DLL return code.

#### Scenario: VAD silence triggers stopped signal
- **WHEN** `ta_poll()` returns `-1` after draining all frames
- **THEN** the audio tick loop triggers the recorder's VAD-stopped transition
- **AND** `mic.audio.end` is sent to the service

#### Scenario: Manual stop does NOT trigger VAD stopped
- **WHEN** `ta_poll()` returns `-2` (manual stop via `ta_stop()`)
- **THEN** the VAD-stopped transition is NOT triggered
- **AND** `mic.audio.end` is sent to the service

### Requirement: Supersede active capture on new start
`ta_start()` called while capture is active SHALL restart capture. The DLL flushes the ring buffer. Lua increments the session ID, and the old session's `mic.audio.end` is NOT sent.

#### Scenario: Rapid start-start
- **WHEN** `ta_start()` is called while a capture is already active
- **THEN** the DLL stops the old capture and starts a new one (ring buffer flushed)
- **AND** Lua assigns a new `session_id`
- **AND** no `mic.audio.end` is sent for the old session

## REMOVED Requirements

### Requirement: WS proxy for Lua traffic
**Reason**: The bridge's WS proxy role is no longer required for mic workflows. Lua communicates directly with `talker_service` via its existing pollnet WebSocket. Audio chunks originate from Lua, not from the bridge.
**Migration**: Lua sends `mic.audio.chunk` and `mic.audio.end` directly to `talker_service` over the existing service channel WebSocket. The bridge may continue proxying non-mic traffic for other use cases but is not part of the mic capture pipeline.

### Requirement: Standalone executable build
**Reason**: The bridge executable is not part of the native mic capture pipeline. Mic capture is handled by `talker_audio.dll` loaded via FFI.
**Migration**: No migration needed — the bridge can retain its build process independently if still used for TTS or proxying.
