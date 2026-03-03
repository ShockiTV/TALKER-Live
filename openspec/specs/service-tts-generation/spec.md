# service-tts-generation

## Purpose

Defines how the Python `talker_service` generates OGG Vorbis audio from dialogue text using pocket_tts and publishes it to the Lua game client for in-engine playback.

## Requirements

### Requirement: pocket_tts model and voice cache in talker_service
When TTS is enabled in the configuration, the talker_service SHALL load the pocket_tts model at startup and populate a voice cache from `.safetensors` files found in the configured voices directory. The voices directory SHALL default to `./voices` relative to the talker_service root (i.e., `talker_service/voices/`). The directory SHALL contain a flat layout of `<theme>.safetensors` files with no subdirectories.

#### Scenario: Service starts with TTS enabled and voices available
- **WHEN** talker_service starts with TTS enabled and `voices/dolg_1.safetensors` exists in `talker_service/voices/`
- **THEN** the TTS model is loaded and `voice_cache["dolg_1"]` contains the voice state

#### Scenario: Service starts with TTS disabled
- **WHEN** talker_service starts with TTS disabled in config
- **THEN** no pocket_tts model is loaded and TTS generation is skipped

#### Scenario: No safetensors files found
- **WHEN** TTS is enabled but the voices directory contains no `.safetensors` files
- **THEN** a warning is logged and TTS is effectively disabled (no audio generated)

### Requirement: Generate OGG Vorbis from dialogue text
When TTS is enabled and a voice is available for the speaker, the TTS module SHALL generate audio from the dialogue text using pocket_tts, peak-normalize the raw float32 24 kHz PCM to ±1.0 (skipping normalization if peak amplitude is below 1e-6), then pipe it through ffmpeg which resamples to 44100 Hz, applies volume boost (configurable via MCM `tts_volume_boost`, default 8.0), and encodes to OGG Vorbis in a single pass. Returns the OGG bytes.

#### Scenario: PCM is peak-normalized before encoding
- **WHEN** pocket_tts produces chunks with a peak amplitude of 0.05
- **THEN** the concatenated PCM buffer is divided by 0.05, resulting in a peak of 1.0
- **AND** the normalized buffer is then passed to ffmpeg with the configured volume boost

#### Scenario: Near-silent audio skips normalization
- **WHEN** pocket_tts produces chunks with a peak amplitude below 1e-6
- **THEN** normalization is skipped (no divide-by-zero)
- **AND** the raw buffer is passed to ffmpeg as-is

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
After the dialogue generator produces dialogue text, the event handler SHALL generate TTS audio (if `tts_engine` is injected and a voice is available) and publish `tts.audio` to the Lua client via the service channel. The payload SHALL include `speaker_id`, `audio_b64`, `voice_id`, `dialogue`, `dialogue_id` (monotonic counter for correlation), `create_event`, and `event_context`. When TTS engine is not injected (`None`) or generation fails, `dialogue.display` is published as fallback. There SHALL be no secondary `tts.speak` fallback to the bridge — the service is the sole TTS provider.

#### Scenario: Dialogue with TTS audio
- **WHEN** dialogue "Stay sharp." is generated for speaker_id "5" with sound_prefix "dolg_1" and dialogue_id 3
- **THEN** `tts.audio` is published with `{ speaker_id: "5", audio_b64: "<base64_ogg>", voice_id: "dolg_1", dialogue: "Stay sharp.", dialogue_id: 3, create_event: true, event_context: {...} }`

#### Scenario: TTS engine not injected falls back to dialogue.display only
- **WHEN** `tts_engine` is None (not injected or TTS disabled)
- **THEN** `dialogue.display` is published instead
- **AND** no `tts.speak` message is sent to the bridge

#### Scenario: TTS generation failure falls back to dialogue.display
- **WHEN** `tts_engine.generate_audio()` throws an error or returns None
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
The service SHALL resolve a `voice_id` for each speaker by using the `sound_prefix` field from the speaker's character data in the `candidates` list. The `sound_prefix` (e.g. `"stalker_1"`, `"dolg_3"`) maps directly to pocket_tts `.safetensors` file stems. If the speaker has no `sound_prefix` or it is empty, the TTS engine's `_resolve_voice()` fallback logic SHALL be used (first available voice in cache). If no voice mapping exists and the voice cache is empty, TTS SHALL be skipped and `dialogue.display` published instead.

#### Scenario: voice_id resolved from candidate sound_prefix
- **WHEN** the chosen speaker has `sound_prefix: "dolg_3"` in the candidates list
- **THEN** `"dolg_3"` is used as `voice_id` for TTS generation

#### Scenario: No voice available for speaker
- **WHEN** the speaker has no resolvable `sound_prefix` and the voice cache is empty
- **THEN** TTS is skipped and `dialogue.display` is published instead

### Requirement: pocket_tts is an optional dependency
The talker_service SHALL function normally without pocket_tts installed. If `import pocket_tts` fails, TTS generation SHALL be disabled with a log message. All non-TTS functionality (dialogue generation, memory compression, etc.) SHALL be unaffected. The `tts/__init__.py` module uses a try/except to set `TTS_AVAILABLE = False` when pocket_tts is missing.

#### Scenario: pocket_tts not installed
- **WHEN** talker_service starts and `import pocket_tts` raises ImportError
- **THEN** a warning is logged: "pocket_tts not installed — TTS disabled"
- **AND** dialogue generation continues normally, publishing `dialogue.display`

### Requirement: Volume boost configurable via MCM
The TTS volume boost SHALL be configurable via the MCM setting `tts_volume_boost` (range 1.0–15.0, default 8.0). The value is applied as an ffmpeg `-af volume=N` filter during OGG encoding after peak normalization. Changes are propagated at runtime via `config.sync` / `config.update` messages.

#### Scenario: Volume boost updated at runtime
- **WHEN** `config.update` with `key=tts_volume_boost, value=3.0` is received
- **THEN** subsequent TTS audio is encoded with `-af volume=3.0`

#### Scenario: MCM slider range
- **WHEN** the user opens the MCM settings for TALKER
- **THEN** the TTS volume boost slider has a minimum of 1.0, maximum of 15.0, step of 0.5, and default of 8.0

### Requirement: Dialogue ID correlation
Each dialogue publication SHALL be assigned a monotonic `dialogue_id` (incremented per call to `_publish_dialogue`). The `dialogue_id` SHALL be included in both `tts.audio` and `dialogue.display` payloads and logged with `[D#N]` prefix on both Python and Lua sides for end-to-end tracing.

#### Scenario: Sequential dialogue IDs
- **WHEN** three dialogues are published in sequence
- **THEN** they receive dialogue_id 1, 2, 3

#### Scenario: dialogue_id in log output
- **WHEN** dialogue_id 5 is published for speaker "19240"
- **THEN** Python logs `[D#5] Published TTS audio for 19240: ...`
- **AND** Lua logs `[D#5] slot=5 speaker=19240 dialogue='...'`

## Removed Capabilities

### Requirement: Bridge tts.speak fallback from Lua
The Lua `handle_dialogue_display` handler SHALL NOT publish `tts.speak` to the bridge as a fallback when receiving `dialogue.display`. The bridge no longer handles TTS playback. Dialogue display is the terminal action.

### Requirement: Bridge 2D TTS playback
The talker_bridge SHALL NOT contain TTS playback code (`TTSQueue`, `load_voice_cache`, `play_tts`, `_run_tts_task`), the `--tts` CLI flag, or the `tts.speak` local topic handler. All TTS is handled by the talker_service via `tts.audio`.

### Requirement: Lua tts_enabled config getter
The Lua `interface.config` module SHALL NOT expose a `tts_enabled()` getter. TTS enablement is a service-side concern; the Lua client does not need to query it.

### Requirement: Lua voices.lua repository
The `bin/lua/domain/repo/voices.lua` module SHALL NOT exist. Per-character voice ID tracking was superseded by the `voice-profile-store` spec; the service resolves voice IDs from game state data.
