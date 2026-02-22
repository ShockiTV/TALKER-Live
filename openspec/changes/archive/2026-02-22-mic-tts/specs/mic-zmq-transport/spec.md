## ADDED Requirements

### Requirement: tts.speak topic sent from Lua to mic_python
Lua SHALL publish `tts.speak` on ZMQ port 5555 when dequeuing a TTS task. The payload SHALL include `voice_id` (string), `text` (string), and `speaker_id` (string).

#### Scenario: tts.speak payload is well-formed
- **WHEN** Lua dequeues a TTS task for speaker `"npc_wolf"` with voice `"dolg_3"` and dialogue `"Stay sharp."`
- **THEN** the published message is `tts.speak {"voice_id":"dolg_3","text":"Stay sharp.","speaker_id":"npc_wolf"}`

### Requirement: tts.started topic sent from mic_python to Lua
mic_python SHALL publish `tts.started` on ZMQ port 5557 immediately before beginning audio playback. The payload SHALL include `speaker_id` (string).

#### Scenario: tts.started is published before first audio chunk
- **WHEN** mic_python begins streaming audio for `speaker_id = "npc_wolf"`
- **THEN** `tts.started {"speaker_id":"npc_wolf"}` is published before any audio output occurs

### Requirement: tts.done topic sent from mic_python to Lua
mic_python SHALL publish `tts.done` on ZMQ port 5557 after the last audio chunk has been played and the sounddevice stream is closed. The payload SHALL include `speaker_id` (string).

#### Scenario: tts.done is published after playback completes
- **WHEN** mic_python finishes streaming all audio chunks for `speaker_id = "npc_wolf"`
- **THEN** `tts.done {"speaker_id":"npc_wolf"}` is published

### Requirement: Lua dialogue queue gates HUD display on tts.started
When TTS is enabled, Lua SHALL NOT display HUD text for a `dialogue.display` command immediately. Instead it SHALL enqueue the item (speaker_id, dialogue, voice_id), publish `tts.speak` for the head-of-queue item, and display HUD text only upon receiving `tts.started` for that speaker_id. When TTS is disabled, existing immediate-display behaviour is unchanged.

#### Scenario: HUD shown on tts.started when TTS enabled
- **WHEN** `dialogue.display` is received, TTS is enabled, and subsequent `tts.started` arrives
- **THEN** HUD text is displayed at the moment `tts.started` is processed, not before

#### Scenario: HUD shown immediately when TTS disabled
- **WHEN** `dialogue.display` is received and TTS is disabled
- **THEN** HUD text is displayed immediately (no change from current behaviour)

### Requirement: Lua TTS queue advances on tts.done or timeout
After receiving `tts.done`, Lua SHALL remove the completed item from the queue and publish `tts.speak` for the next item if present. If `tts.started` is not received within 30 seconds of publishing `tts.speak`, Lua SHALL drop the item, log a warning, and advance the queue.

#### Scenario: Queue advances on tts.done
- **WHEN** `tts.done` is received and the queue contains a second item
- **THEN** the completed item is removed and `tts.speak` is published for the next item

#### Scenario: Timeout drops stuck item and advances queue
- **WHEN** `tts.speak` is published and `tts.started` is not received within 30 seconds
- **THEN** a warning is logged, the item is dropped, and the queue advances

#### Scenario: Queue overflow drops oldest excess items
- **WHEN** the Lua TTS queue already contains 5 items and a new `dialogue.display` arrives
- **THEN** the new item is dropped and a warning is logged

### Requirement: mic_python subscribes to tts.* topic prefix
When launched with `--tts`, mic_python SHALL add `tts.` to its ZMQ subscription filter on port 5555, in addition to the existing `mic.` filter.

#### Scenario: tts.speak is received by mic_python
- **WHEN** Lua publishes `tts.speak {...}` on port 5555
- **THEN** mic_python (started with `--tts`) receives and processes the message

### Requirement: Lua subscribes to tts.* topic prefix from mic_python
`talker_zmq_integration.script` SHALL subscribe to `tts.` on port 5557 (mic_python PUB), routing `tts.started` and `tts.done` to registered command handlers.

#### Scenario: Lua receives tts.started
- **WHEN** mic_python publishes `tts.started {"speaker_id":"npc_wolf"}` on port 5557
- **THEN** Lua dispatches to the `tts.started` handler which triggers HUD display
