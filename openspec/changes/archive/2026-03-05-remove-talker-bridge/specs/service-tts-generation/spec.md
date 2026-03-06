# service-tts-generation

## MODIFIED Requirements

### Requirement: Publish tts.audio after dialogue generation
After the dialogue generator produces dialogue text, the event handler SHALL generate TTS audio (if `tts_engine` is injected and a voice is available) and publish `tts.audio` to the Lua client via the WebSocket connection. The payload SHALL include `speaker_id`, `audio_b64`, `voice_id`, `dialogue`, `dialogue_id` (monotonic counter for correlation), `create_event`, and `event_context`. When TTS engine is not injected (`None`) or generation fails, `dialogue.display` is published as fallback. There is no bridge in the architecture — audio flows directly from service to Lua.

#### Scenario: Dialogue with TTS audio
- **WHEN** dialogue "Stay sharp." is generated for speaker_id "5" with sound_prefix "dolg_1" and dialogue_id 3
- **THEN** `tts.audio` is published directly to Lua with `{ speaker_id: "5", audio_b64: "<base64_ogg>", voice_id: "dolg_1", dialogue: "Stay sharp.", dialogue_id: 3, create_event: true, event_context: {...} }`

#### Scenario: TTS engine not injected falls back to dialogue.display only
- **WHEN** `tts_engine` is None (not injected or TTS disabled)
- **THEN** `dialogue.display` is published instead
- **AND** no secondary fallback exists (no bridge, no `tts.speak`)
