# mic-zmq-transport

## Purpose

Defines the ZMQ-based IPC contract between the Lua game layer and `mic_python` — the local microphone capture process. mic_python is a standalone ZMQ peer (separate from `talker_service`) that subscribes to Lua's PUB socket for recording commands and publishes status/results back via its own PUB socket on port 5557.

## Requirements

### Requirement: mic_python ZMQ subscriber receives commands from Lua

mic_python SHALL create a ZMQ SUB socket that connects to the game's PUB endpoint (tcp://127.0.0.1:5555) and subscribes only to topics prefixed with `mic.`.

#### Scenario: mic_python subscribes to mic topics on startup
- **WHEN** mic_python starts
- **THEN** it SHALL create a SUB socket connected to tcp://127.0.0.1:5555
- **AND** the subscription filter SHALL be `mic.`
- **AND** all non-mic topics SHALL be ignored

#### Scenario: mic_python receives mic.start command
- **WHEN** Lua publishes a `mic.start` message with payload `{ lang, prompt }`
- **THEN** mic_python SHALL parse the topic and JSON payload
- **AND** mic_python SHALL begin a recording session with the specified language and prompt

#### Scenario: mic_python receives mic.stop command
- **WHEN** Lua publishes a `mic.stop` message
- **THEN** mic_python SHALL stop any active recording session

### Requirement: mic_python ZMQ publisher sends results to Lua

mic_python SHALL create a ZMQ PUB socket bound to tcp://*:5557 for publishing status updates and transcription results back to the game.

#### Scenario: mic_python binds PUB socket on startup
- **WHEN** mic_python starts
- **THEN** it SHALL bind a PUB socket to tcp://*:5557
- **AND** the port SHALL be configurable via command-line argument

#### Scenario: mic_python publishes LISTENING status
- **WHEN** a recording session begins
- **THEN** mic_python SHALL publish `mic.status { "status": "LISTENING" }` on the PUB socket

#### Scenario: mic_python publishes TRANSCRIBING status
- **WHEN** recording stops (silence detected or manual stop) and transcription begins
- **THEN** mic_python SHALL publish `mic.status { "status": "TRANSCRIBING" }` on the PUB socket

#### Scenario: mic_python publishes transcription result
- **WHEN** transcription completes successfully
- **THEN** mic_python SHALL publish `mic.result { "text": "<transcribed text>" }` on the PUB socket

### Requirement: mic_python uses synchronous ZMQ message loop

mic_python SHALL use a synchronous ZMQ receive loop (blocking recv with timeout) instead of file-system watching.

#### Scenario: Main loop processes messages
- **WHEN** mic_python is running
- **THEN** it SHALL block on `zmq_recv()` with a timeout (e.g., 1000ms)
- **AND** on timeout it SHALL loop back and check again
- **AND** on receiving a message it SHALL dispatch to the appropriate handler

#### Scenario: Graceful shutdown
- **WHEN** mic_python receives KeyboardInterrupt or SIGINT
- **THEN** it SHALL close both ZMQ sockets
- **AND** it SHALL terminate the ZMQ context
- **AND** it SHALL exit cleanly

### Requirement: mic_python wire format is simple topic+JSON

mic_python SHALL send and receive messages in the format `<topic> <json-payload>` where the JSON payload is a flat object (no envelope wrapping with topic/timestamp fields).

#### Scenario: Outgoing message format
- **WHEN** mic_python publishes a message
- **THEN** the raw ZMQ message SHALL be `mic.status {"status":"LISTENING"}` (topic, space, JSON)

#### Scenario: Incoming message parsing
- **WHEN** mic_python receives a raw ZMQ message
- **THEN** it SHALL split on the first space to extract topic and JSON payload
- **AND** it SHALL parse the JSON payload into a dict

### Requirement: Audio capture and transcription unchanged

The recording (recorder.py) and transcription providers (whisper_api.py, whisper_local.py, gemini_proxy.py) SHALL NOT be modified. mic_python SHALL continue to support all three transcription providers via command-line argument.

#### Scenario: Provider selection preserved
- **WHEN** mic_python is launched with a provider argument (e.g., `gemini_proxy`, `whisper_local`, `whisper_api`)
- **THEN** the specified transcription provider SHALL be used for all recording sessions

#### Scenario: Recording session flow preserved
- **WHEN** a mic.start command is received
- **THEN** mic_python SHALL call `recorder.start_recording()` with silence grace period
- **AND** mic_python SHALL wait for silence detection to stop recording
- **AND** mic_python SHALL call the transcription provider with the audio file

### Requirement: Lua microphone module uses ZMQ for commands

The Lua microphone module (`bin/lua/infra/mic/microphone.lua`) SHALL send commands via `bridge.publish()` instead of writing to temp files via `file_io.override_temp()`.

#### Scenario: mic.start sent via ZMQ
- **WHEN** `mic.start(transcription_prompt)` is called in Lua
- **THEN** the module SHALL call `bridge.publish("mic.start", { lang = lang_code, prompt = transcription_prompt })`
- **AND** the module SHALL NOT write to any temp file

#### Scenario: mic.stop sent via ZMQ
- **WHEN** `mic.stop()` is called in Lua
- **THEN** the module SHALL call `bridge.publish("mic.stop", {})`
- **AND** the module SHALL NOT write to any temp file

#### Scenario: mic.status received via ZMQ handler
- **WHEN** mic_python publishes `mic.status { status: "LISTENING" }`
- **THEN** the Lua microphone module SHALL invoke the `opts.on_status(status)` callback with the received status string
- **AND** the callback SHALL be provided by the caller at `mic.start()` invocation time

#### Scenario: mic.result received via ZMQ handler
- **WHEN** mic_python publishes `mic.result { text: "transcribed text" }`
- **THEN** the Lua microphone module SHALL invoke the `opts.on_result(text)` callback with the transcribed text
- **AND** the mic_on state SHALL be set to false
- **AND** the per-session `mic.status` and `mic.result` handlers SHALL be unregistered

### Requirement: Lua recorder uses push-based results instead of polling

The Lua recorder module (`bin/lua/interface/recorder.lua`) SHALL receive transcription results via ZMQ push notifications instead of polling temp files in a loop.

#### Scenario: Recorder registers ZMQ handlers on start
- **WHEN** `recorder.start(callback)` is called
- **THEN** the recorder SHALL register ZMQ handlers for `mic.status` and `mic.result` via `bridge.register_handler()`
- **AND** the recorder SHALL send `mic.start` via the microphone module

#### Scenario: Status displayed to player
- **WHEN** a `mic.status` message is received by the handler
- **THEN** the recorder SHALL display the status to the player (e.g., "LISTENING", "TRANSCRIBING")

#### Scenario: Transcription result triggers callback
- **WHEN** a `mic.result` message is received by the handler
- **THEN** the recorder SHALL invoke the callback function with the transcribed text
- **AND** the recorder SHALL clean up handlers

### Requirement: files.py is removed from mic_python

The file `mic_python/python/files.py` SHALL be deleted. No code SHALL read or write temp files for mic IPC.

#### Scenario: No temp file usage
- **WHEN** mic_python is running
- **THEN** it SHALL NOT read from or write to `%TEMP%\talker_mic_io_commands`
- **AND** it SHALL NOT read from or write to `%TEMP%\talker_mic_io_transcription`

### Requirement: mic_python dependencies updated

mic_python requirements SHALL replace `watchdog` with `pyzmq`. The PyInstaller build SHALL include `zmq` as a hidden import.

#### Scenario: requirements.txt updated
- **WHEN** mic_python dependencies are installed
- **THEN** `pyzmq` SHALL be listed in requirements.txt
- **AND** `watchdog` SHALL NOT be listed

#### Scenario: PyInstaller build includes zmq
- **WHEN** build.bat is executed
- **THEN** the PyInstaller command SHALL include `--hidden-import=zmq`
