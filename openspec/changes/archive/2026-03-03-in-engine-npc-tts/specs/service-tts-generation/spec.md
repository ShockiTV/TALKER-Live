# service-tts-generation (delta)

## MODIFIED Requirements

### Requirement: Voice ID resolution from game state

The service SHALL resolve a `voice_id` for each speaker by using the `sound_prefix` field from the speaker's character data in the `candidates` list. The `sound_prefix` (e.g. `"stalker_1"`, `"dolg_3"`) maps directly to pocket_tts `.safetensors` file stems. If the speaker has no `sound_prefix` or it is empty, the TTS engine's `_resolve_voice()` fallback logic SHALL be used (first available voice in cache). If no voice mapping exists and the voice cache is empty, TTS SHALL be skipped and `dialogue.display` published instead.

#### Scenario: voice_id resolved from candidate sound_prefix

- **WHEN** the chosen speaker has `sound_prefix: "dolg_3"` in the candidates list
- **THEN** `"dolg_3"` is used as `voice_id` for TTS generation

#### Scenario: No voice available for speaker

- **WHEN** the speaker has no resolvable `sound_prefix` and the voice cache is empty
- **THEN** TTS is skipped and `dialogue.display` is published instead

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
