# service-tts-generation (delta)

## MODIFIED

### Requirement: pocket_tts model and voice cache in talker_service
When TTS is enabled in the configuration, the talker_service SHALL load the pocket_tts model at startup and populate a voice cache from `.safetensors` files found in the configured voices directory. The voices directory SHALL default to `./voices` relative to the talker_service root (i.e., `talker_service/voices/`). The directory SHALL contain a flat layout of `<theme>.safetensors` files with no subdirectories.

#### Scenario: Service starts with TTS enabled and voices available
- **WHEN** talker_service starts with TTS enabled and `voices/dolg_1.safetensors` exists in `talker_service/voices/`
- **THEN** the TTS model is loaded and `voice_cache["dolg_1"]` contains the voice state

#### Scenario: Service starts with TTS disabled
- **WHEN** talker_service starts with TTS disabled in config
- **THEN** no pocket_tts model is loaded and TTS generation is skipped

#### Scenario: No safetensors files found
- **WHEN** TTS is enabled but `talker_service/voices/` contains no `.safetensors` files
- **THEN** a warning is logged and TTS is effectively disabled (no audio generated)

### Requirement: Publish tts.audio after dialogue generation
After the dialogue generator produces dialogue text, the service SHALL generate TTS audio (if TTS is enabled and a voice is available) and publish `tts.audio` to the Lua client via the service channel. The payload SHALL include `speaker_id`, `audio_b64`, `voice_id`, `dialogue`, and `dialogue_id`. When TTS is disabled or unavailable, `dialogue.display` is published as fallback. There SHALL be no secondary `tts.speak` fallback to the bridge — the service is the sole TTS provider.

#### Scenario: Dialogue with TTS audio
- **WHEN** dialogue "Stay sharp." is generated for speaker_id "5" with voice "dolg_1" and dialogue_id 3
- **THEN** `tts.audio` is published with `{ speaker_id: "5", audio_b64: "<base64_ogg>", voice_id: "dolg_1", dialogue: "Stay sharp.", dialogue_id: 3 }`

#### Scenario: TTS disabled falls back to dialogue.display only
- **WHEN** TTS is disabled or no voice is available
- **THEN** `dialogue.display` is published instead
- **AND** no `tts.speak` message is sent to the bridge

#### Scenario: TTS generation failure falls back to dialogue.display
- **WHEN** pocket_tts throws an error during generation
- **THEN** `dialogue.display` is published as fallback
- **AND** the error is logged

## REMOVED

### Requirement: Bridge tts.speak fallback from Lua
The Lua `handle_dialogue_display` handler SHALL NOT publish `tts.speak` to the bridge as a fallback when receiving `dialogue.display`. The bridge no longer handles TTS playback. Dialogue display is the terminal action.

### Requirement: Bridge 2D TTS playback
The talker_bridge SHALL NOT contain TTS playback code (`TTSQueue`, `load_voice_cache`, `play_tts`, `_run_tts_task`), the `--tts` CLI flag, or the `tts.speak` local topic handler. All TTS is handled by the talker_service via `tts.audio`.

### Requirement: Lua tts_enabled config getter
The Lua `interface.config` module SHALL NOT expose a `tts_enabled()` getter. TTS enablement is a service-side concern; the Lua client does not need to query it.

### Requirement: Lua voices.lua repository
The `bin/lua/domain/repo/voices.lua` module SHALL NOT exist. Per-character voice ID tracking was superseded by the `voice-profile-store` spec; the service resolves voice IDs from game state data.
