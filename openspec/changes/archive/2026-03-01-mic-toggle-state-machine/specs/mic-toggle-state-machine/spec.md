## ADDED Requirements

### Requirement: Toggle state machine with three states
`recorder.lua` SHALL implement a toggle state machine with three states: `idle`, `capturing`, and `transcribing`. The `toggle(callback)` function SHALL transition between states based on the current state.

#### Scenario: Toggle from idle starts capture
- **WHEN** `recorder.toggle(callback)` is called
- **AND** the current state is `idle`
- **THEN** `microphone.start_capture()` is called
- **AND** `bridge_channel.publish("mic.start", ...)` is sent
- **AND** the state transitions to `capturing`

#### Scenario: Toggle from capturing stops and transcribes
- **WHEN** `recorder.toggle(callback)` is called
- **AND** the current state is `capturing`
- **THEN** `microphone.stop_capture()` is called
- **AND** `bridge_channel.publish("mic.stop", {})` is sent
- **AND** the state transitions to `transcribing`

#### Scenario: Toggle from transcribing starts new capture
- **WHEN** `recorder.toggle(callback)` is called
- **AND** the current state is `transcribing`
- **THEN** a new capture session starts (same as toggle from idle)
- **AND** the state transitions to `capturing`
- **AND** the previous transcription callback remains active for delivery

### Requirement: Permanent handler registration
`recorder.lua` SHALL register permanent handlers via `bridge_channel.on()` for `mic.status`, `mic.stopped`, and `mic.result` topics. These handlers SHALL NOT be session-scoped and SHALL persist across multiple recording sessions.

#### Scenario: Handlers survive session completion
- **WHEN** a capture session completes (mic.result received)
- **AND** a new session is started
- **THEN** the `mic.status`, `mic.stopped`, and `mic.result` handlers are still active without re-registration

### Requirement: Callback delivery on mic.result
When `mic.result` is received with a non-empty `text` field, the recorder SHALL invoke the most recently registered callback with the transcription text and transition to `idle`.

#### Scenario: Result delivered and state transitions
- **WHEN** `mic.result` arrives with `{text: "Hello world"}`
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

### Requirement: VAD auto-stop transition via mic.stopped
When `mic.stopped` is received while in `capturing` state, the recorder SHALL transition to `transcribing` (STT is already in progress on the service side).

#### Scenario: VAD silence triggers state transition
- **WHEN** `mic.stopped` arrives with `{reason: "vad"}`
- **AND** the current state is `capturing`
- **THEN** `microphone.on_stopped()` is called
- **AND** the state transitions to `transcribing`

#### Scenario: mic.stopped while not capturing is ignored
- **WHEN** `mic.stopped` arrives
- **AND** the current state is NOT `capturing`
- **THEN** no state change occurs

### Requirement: HUD priority — RECORDING suppresses mic.status
The `mic.status` handler SHALL suppress incoming status updates when the current state is `capturing`. The "RECORDING" HUD message set by `toggle()` SHALL take priority over any background transcription status.

#### Scenario: mic.status suppressed during capture
- **WHEN** `mic.status` arrives with `{status: "TRANSCRIBING"}`
- **AND** the current state is `capturing`
- **THEN** the HUD message is NOT updated (remains "RECORDING")

#### Scenario: mic.status shown when not capturing
- **WHEN** `mic.status` arrives with `{status: "TRANSCRIBING"}`
- **AND** the current state is NOT `capturing`
- **THEN** the HUD message is updated to "TRANSCRIBING"

### Requirement: Thin microphone hardware wrapper
`microphone.lua` SHALL expose `start_capture(context_type)`, `stop_capture()`, `is_recording()`, and `on_stopped()` as a thin hardware abstraction with no session management or state machine logic.

#### Scenario: start_capture sets recording flag
- **WHEN** `microphone.start_capture("dialogue")` is called
- **THEN** `microphone.is_recording()` returns `true`

#### Scenario: stop_capture clears recording flag
- **WHEN** `microphone.stop_capture()` is called
- **THEN** `microphone.is_recording()` returns `false`

#### Scenario: on_stopped resets recording without publishing
- **WHEN** `microphone.on_stopped()` is called while recording
- **THEN** `microphone.is_recording()` returns `false`
- **AND** no message is published to the bridge

### Requirement: Game script calls toggle
`talker_input_mic.script` SHALL call `recorder.toggle(callback)` on key press, replacing the previous `recorder.start()` call.

#### Scenario: Key press invokes toggle
- **WHEN** the player presses the mic capture key
- **THEN** `recorder.toggle(transcribe_finished_callback)` is called

### Requirement: Test reset function
`recorder._reset()` SHALL reset the recorder state to `idle` for test isolation. This replaces the removed `recorder.cancel()`.

#### Scenario: Reset clears state
- **WHEN** `recorder._reset()` is called
- **THEN** `recorder.state()` returns `"idle"`
