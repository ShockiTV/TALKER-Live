# mic-toggle-state-machine (delta)

## MODIFIED Requirements

### Requirement: Toggle state machine with three states
`recorder.lua` SHALL implement a toggle state machine with three states: `idle`, `capturing`, and `transcribing`. The `toggle(callback)` function SHALL transition between states based on the current state.

#### Scenario: Toggle from idle starts capture
- **WHEN** `recorder.toggle(callback)` is called
- **AND** the current state is `idle`
- **THEN** `microphone.start_capture()` is called (which calls `ta_start()` via FFI)
- **AND** the state transitions to `capturing`

#### Scenario: Toggle from capturing stops and transcribes
- **WHEN** `recorder.toggle(callback)` is called
- **AND** the current state is `capturing`
- **THEN** `microphone.stop_capture()` is called (which calls `ta_stop()` via FFI)
- **AND** the state transitions to `transcribing`

#### Scenario: Toggle from transcribing starts new capture
- **WHEN** `recorder.toggle(callback)` is called
- **AND** the current state is `transcribing`
- **THEN** a new capture session starts (same as toggle from idle)
- **AND** the state transitions to `capturing`
- **AND** the previous transcription callback remains active for delivery

### Requirement: VAD auto-stop transition via ta_poll return code
When the audio tick loop detects `ta_poll() == -1` (VAD silence), it SHALL notify the recorder to transition from `capturing` to `transcribing`. This replaces the previous `bridge_channel.on("mic.stopped", ...)` handler.

#### Scenario: VAD silence triggers state transition
- **WHEN** the audio tick loop detects `ta_poll()` returned `-1`
- **AND** the recorder's current state is `capturing`
- **THEN** `microphone.on_stopped()` is called
- **AND** the state transitions to `transcribing`

#### Scenario: VAD signal while not capturing is ignored
- **WHEN** the audio tick loop detects `ta_poll()` returned `-1`
- **AND** the recorder's current state is NOT `capturing`
- **THEN** no state change occurs

### Requirement: Callback delivery on mic.result
When `mic.result` is received over the WebSocket from `talker_service`, the recorder SHALL invoke the most recently registered callback with the transcription text and transition to `idle`.

#### Scenario: Result delivered and state transitions
- **WHEN** `mic.result` arrives over the service channel WebSocket with `{text: "Hello world"}`
- **AND** the current state is `transcribing`
- **THEN** `callback("Hello world")` is invoked
- **AND** the state transitions to `idle`

#### Scenario: Result during capturing is ignored
- **WHEN** `mic.result` arrives (from a previous session)
- **AND** the current state is `capturing`
- **THEN** the callback is invoked (delivering the old result)
- **AND** the state remains `capturing`

#### Scenario: Empty result is ignored
- **WHEN** `mic.result` arrives with `{text: ""}`
- **THEN** the callback is NOT invoked

### Requirement: Handler registration via service channel
`recorder.lua` SHALL register a permanent handler via the service channel (not bridge channel) for the `mic.result` topic. The `mic.stopped` and `mic.status` bridge channel handlers are removed — VAD auto-stop is handled via `ta_poll()` return codes and status updates come from the service channel.

#### Scenario: mic.result handler registered on service channel
- **WHEN** `recorder.register_handlers()` is called
- **THEN** a handler for `mic.result` is registered on the service channel
- **AND** no handlers are registered on the bridge channel for mic topics

#### Scenario: Handlers survive session completion
- **WHEN** a capture session completes (mic.result received)
- **AND** a new session is started
- **THEN** the `mic.result` handler is still active without re-registration

### Requirement: HUD priority — RECORDING suppresses mic.status
The `mic.status` handler (if present on the service channel) SHALL suppress incoming status updates when the current state is `capturing`. The "RECORDING" HUD message set by `toggle()` SHALL take priority over any background transcription status.

#### Scenario: mic.status suppressed during capture
- **WHEN** `mic.status` arrives with `{status: "TRANSCRIBING"}`
- **AND** the current state is `capturing`
- **THEN** the HUD message is NOT updated (remains "RECORDING")

#### Scenario: mic.status shown when not capturing
- **WHEN** `mic.status` arrives with `{status: "TRANSCRIBING"}`
- **AND** the current state is NOT `capturing`
- **THEN** the HUD message is updated to "TRANSCRIBING"

### Requirement: Thin microphone hardware wrapper
`microphone.lua` SHALL expose `start_capture(context_type)`, `stop_capture()`, `is_recording()`, and `on_stopped()` as a thin hardware abstraction. Internally, these call `ta_start()`, `ta_stop()`, etc. via FFI instead of publishing bridge messages.

#### Scenario: start_capture calls ta_start
- **WHEN** `microphone.start_capture("dialogue")` is called
- **THEN** `ta_start()` is called via FFI
- **AND** `microphone.is_recording()` returns `true`

#### Scenario: stop_capture calls ta_stop
- **WHEN** `microphone.stop_capture()` is called
- **THEN** `ta_stop()` is called via FFI
- **AND** `microphone.is_recording()` returns `false`

#### Scenario: on_stopped resets recording without FFI call
- **WHEN** `microphone.on_stopped()` is called while recording
- **THEN** `microphone.is_recording()` returns `false`
- **AND** no FFI call is made (DLL already stopped via VAD)

### Requirement: Game script calls toggle
`talker_input_mic.script` SHALL call `recorder.toggle(callback)` on key press.

#### Scenario: Key press invokes toggle
- **WHEN** the player presses the mic capture key
- **THEN** `recorder.toggle(transcribe_finished_callback)` is called

### Requirement: Test reset function
`recorder._reset()` SHALL reset the recorder state to `idle` for test isolation.

#### Scenario: Reset clears state
- **WHEN** `recorder._reset()` is called
- **THEN** `recorder.state()` returns `"idle"`

## REMOVED Requirements

### Requirement: Permanent handler registration
**Reason**: The bridge channel handlers for `mic.status`, `mic.stopped`, and `mic.result` are replaced. `mic.stopped` is now signaled via `ta_poll()` return code `-1`. `mic.result` comes over the service channel. `mic.status` is handled via the service channel if needed.
**Migration**: Replace `bridge_channel.on("mic.stopped", ...)` with poll-loop detection of `ta_poll() == -1`. Replace `bridge_channel.on("mic.result", ...)` with `service_channel.on("mic.result", ...)`.
