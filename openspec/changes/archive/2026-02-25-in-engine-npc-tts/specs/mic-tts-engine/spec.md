## MODIFIED Requirements

### Requirement: tts.speak triggers streamed audio playback on desktop speakers

When the mic channel is active AND the `--tts` flag was passed AND in-engine TTS is NOT available, the `tts.speak` handler SHALL stream audio through desktop speakers as a fallback path.

When in-engine TTS is active (the service publishes `tts.audio` to the game client), the mic channel's `tts.speak` handler is NOT invoked for that dialogue — the audio plays through the game engine instead.

#### Scenario: In-engine TTS active, mic channel not used for playback

- **WHEN** the Python service generates a `tts.audio` message for a dialogue line
- **THEN** the service does NOT publish `tts.speak` to the mic channel for that same line
- **AND** audio plays in-engine on the NPC game object

#### Scenario: In-engine TTS unavailable, mic channel fallback

- **WHEN** the Python service cannot generate TTS audio (pocket_tts not loaded or voice not found)
- **AND** the mic channel is connected with `--tts` enabled
- **THEN** the service publishes `tts.speak` to the mic channel as before
- **AND** audio plays through desktop speakers via sounddevice

### Requirement: Voice export script remains unchanged

The `export_voices.bat` script and voice file format (`.safetensors`) remain unchanged. Voice files are used by both the in-engine TTS path (in `talker_service`) and the mic fallback path (in `mic_python`).

#### Scenario: Voice files shared between paths

- **WHEN** a voice file is exported via `export_voices.bat`
- **THEN** it can be loaded by either `talker_service` or `mic_python` without modification
