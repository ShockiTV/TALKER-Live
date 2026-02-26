# service-tts-generation

## Purpose

Defines how the Python `talker_service` generates OGG Vorbis audio from dialogue text using pocket_tts and publishes it to the Lua game client for in-engine playback.

## Requirements

### Requirement: pocket_tts model and voice cache in talker_service
When TTS is enabled in the configuration, the talker_service SHALL load the pocket_tts model at startup and populate a voice cache from `.safetensors` files found in the configured voices directory. The voices directory SHALL default to `talker_bridge/voices/` relative to the project root.

#### Scenario: Service starts with TTS enabled and voices available
- **WHEN** talker_service starts with TTS enabled and `voices/dolg_1.safetensors` exists
- **THEN** the TTS model is loaded and `voice_cache["dolg_1"]` contains the voice state

#### Scenario: Service starts with TTS disabled
- **WHEN** talker_service starts with TTS disabled in config
- **THEN** no pocket_tts model is loaded and TTS generation is skipped

#### Scenario: No safetensors files found
- **WHEN** TTS is enabled but the voices directory contains no `.safetensors` files
- **THEN** a warning is logged and TTS is effectively disabled (no audio generated)

### Requirement: Generate OGG Vorbis from dialogue text
When TTS is enabled and a voice is available for the speaker, the TTS module SHALL generate audio from the dialogue text using pocket_tts, pipe the raw float32 24 kHz PCM through ffmpeg which resamples to 44100 Hz, applies volume boost (configurable via MCM `tts_volume_boost`, default 4.0), and encodes to OGG Vorbis in a single pass. Returns the OGG bytes.

#### Scenario: Successful OGG generation
- **WHEN** `generate_audio("Stay sharp.", "dolg_1")` is called with a cached voice
- **THEN** the returned bytes are a valid OGG Vorbis file at 44100 Hz containing synthesized speech

#### Scenario: Unknown voice_id falls back
- **WHEN** `generate_audio("text", "unknown_voice")` is called
- **THEN** the first available voice in cache is used
- **AND** a warning is logged

#### Scenario: Empty text returns None
- **WHEN** `generate_audio("", "dolg_1")` is called
- **THEN** None is returned and no audio is generated

### Requirement: Base64 encode OGG for wire transport
After generating OGG bytes, the TTS module SHALL base64-encode the bytes for inclusion in the WS JSON envelope. The encoding SHALL use standard base64 (RFC 4648).

#### Scenario: OGG bytes are base64 encoded
- **WHEN** 60KB of OGG bytes are generated
- **THEN** the base64 output is approximately 80KB
- **AND** it decodes back to the original bytes

### Requirement: Publish tts.audio after dialogue generation
After the dialogue generator produces dialogue text, the service SHALL generate TTS audio (if TTS is enabled and a voice is available) and publish `tts.audio` to the Lua client via the service channel. The payload SHALL include `speaker_id`, `audio_b64`, `voice_id`, `dialogue`, and `dialogue_id` (monotonic counter for correlation).

#### Scenario: Dialogue with TTS audio
- **WHEN** dialogue "Stay sharp." is generated for speaker_id "5" with voice "dolg_1" and dialogue_id 3
- **THEN** `tts.audio` is published with `{ speaker_id: "5", audio_b64: "<base64_ogg>", voice_id: "dolg_1", dialogue: "Stay sharp.", dialogue_id: 3 }`

#### Scenario: TTS disabled falls back to dialogue.display
- **WHEN** TTS is disabled or no voice is available
- **THEN** `dialogue.display` is published instead (existing behavior unchanged)

#### Scenario: TTS generation failure falls back to dialogue.display
- **WHEN** pocket_tts throws an error during generation
- **THEN** `dialogue.display` is published as fallback
- **AND** the error is logged

### Requirement: TTS generation SHALL NOT block the event loop
TTS audio generation (pocket_tts inference + ffmpeg encoding) SHALL run in a single-threaded executor (`max_workers=1`) to avoid blocking the asyncio event loop. The executor is single-threaded because pocket_tts is NOT thread-safe. On timeout, the executor is recycled (abandoned and replaced) so subsequent calls are not blocked behind a stuck thread.

#### Scenario: Event loop remains responsive during TTS
- **WHEN** TTS generation takes 3 seconds for a long dialogue line
- **THEN** heartbeat and other WS messages continue to be processed without delay

#### Scenario: TTS timeout triggers executor recycling
- **WHEN** TTS generation exceeds TTS_TIMEOUT_S (30 seconds)
- **THEN** the cancellation event is set, the stuck executor is abandoned, a fresh executor is created
- **AND** subsequent TTS calls proceed on the new executor

### Requirement: Voice ID resolution from game state
The service SHALL resolve a `voice_id` for each speaker by using the `voice_id` field from the speaker's state data. If no voice mapping exists, TTS SHALL be skipped for that speaker and `dialogue.display` published instead.

#### Scenario: voice_id provided in event data
- **WHEN** the speaker's event data includes `voice_id: "dolg_3"`
- **THEN** `dolg_3` is used for TTS generation

#### Scenario: No voice available for speaker
- **WHEN** the speaker has no resolvable voice_id and no fallback exists
- **THEN** TTS is skipped and `dialogue.display` is published instead

### Requirement: pocket_tts is an optional dependency
The talker_service SHALL function normally without pocket_tts installed. If `import pocket_tts` fails, TTS generation SHALL be disabled with a log message. All non-TTS functionality (dialogue generation, memory compression, etc.) SHALL be unaffected. The `tts/__init__.py` module uses a try/except to set `TTS_AVAILABLE = False` when pocket_tts is missing.

#### Scenario: pocket_tts not installed
- **WHEN** talker_service starts and `import pocket_tts` raises ImportError
- **THEN** a warning is logged: "pocket_tts not installed — TTS disabled"
- **AND** dialogue generation continues normally, publishing `dialogue.display`

### Requirement: Volume boost configurable via MCM
The TTS volume boost SHALL be configurable via the MCM setting `tts_volume_boost` (range 1.0–5.0, default 4.0). The value is applied as an ffmpeg `-af volume=N` filter during OGG encoding. Changes are propagated at runtime via `config.sync` / `config.update` messages.

#### Scenario: Volume boost updated at runtime
- **WHEN** `config.update` with `key=tts_volume_boost, value=3.0` is received
- **THEN** subsequent TTS audio is encoded with `-af volume=3.0`

### Requirement: Dialogue ID correlation
Each dialogue publication SHALL be assigned a monotonic `dialogue_id` (incremented per call to `_publish_dialogue`). The `dialogue_id` SHALL be included in both `tts.audio` and `dialogue.display` payloads and logged with `[D#N]` prefix on both Python and Lua sides for end-to-end tracing.

#### Scenario: Sequential dialogue IDs
- **WHEN** three dialogues are published in sequence
- **THEN** they receive dialogue_id 1, 2, 3

#### Scenario: dialogue_id in log output
- **WHEN** dialogue_id 5 is published for speaker "19240"
- **THEN** Python logs `[D#5] Published TTS audio for 19240: ...`
- **AND** Lua logs `[D#5] slot=5 speaker=19240 dialogue='...'`
