## ADDED Requirements

### Requirement: Session ID tracking
The bridge AudioStreamer SHALL assign a monotonic integer `session_id` to each capture session. The `session_id` SHALL be included in all `mic.audio.chunk` and `mic.audio.end` messages sent to the service.

#### Scenario: Session ID increments on each start
- **WHEN** `start()` is called
- **THEN** `session_id` increments by 1
- **AND** all subsequent `mic.audio.chunk` messages include the new `session_id`

### Requirement: Publish mic.stopped on VAD auto-stop
The bridge SHALL publish `mic.stopped` to Lua (downstream) when VAD silence detection ends capture, but NOT when capture was manually stopped via `mic.stop`.

#### Scenario: VAD silence publishes mic.stopped
- **WHEN** VAD detects sustained silence and ends capture
- **AND** the capture was NOT manually stopped
- **THEN** `{"t": "mic.stopped", "p": {"reason": "vad"}}` is sent to Lua

#### Scenario: Manual stop does NOT publish mic.stopped
- **WHEN** the user sends `mic.stop` and capture ends
- **THEN** `mic.stopped` is NOT sent to Lua

### Requirement: Supersede active capture on new start
`start()` SHALL supersede any active capture session. The previous capture loop SHALL detect supersession and suppress its `mic.audio.end` send.

#### Scenario: Rapid start-start
- **WHEN** `start()` is called while a capture is already active
- **THEN** the old capture is superseded (no `mic.audio.end` for old session)
- **AND** a new capture begins with a new `session_id`

## MODIFIED Requirements

### Requirement: Audio capture without transcription
`talker_bridge` (formerly `mic_python`) SHALL capture audio from the user's microphone without attempting to transcribe it locally.

#### Scenario: Capturing audio
- **WHEN** the user presses the push-to-talk hotkey (via `mic.start` from Lua)
- **THEN** `talker_bridge` begins recording audio from the default microphone device
- **AND** assigns a new monotonic `session_id` to the capture session

### Requirement: WS proxy for Lua traffic
`talker_bridge` SHALL transparently proxy all non-mic WebSocket messages between Lua and `talker_service`.

#### Scenario: Proxying game events
- **WHEN** Lua sends a message (e.g., `game.event`, `player.dialogue`) to `talker_bridge`
- **AND** the topic is not a mic-handled topic (`mic.start`, `mic.stop`)
- **THEN** `talker_bridge` forwards it to `talker_service` unchanged

#### Scenario: Proxying service responses
- **WHEN** `talker_service` sends a message (e.g., `dialogue.display`, `memory.update`) to `talker_bridge`
- **THEN** `talker_bridge` forwards it to Lua unchanged

## REMOVED Requirements

### Requirement: mic.cancel as a local topic
**Reason**: There is no cancel key in the game. The `mic.cancel` topic was unreachable dead code. Bridge-internal `cancel()` is kept only for shutdown cleanup but is not a WS topic.
**Migration**: Remove any references to `mic.cancel` from Lua code. Use `mic.stop` to end capture.
