# tts-dialogue-dispatch

## Purpose

Conditional TTS-or-text dispatch logic in the event handler. After generating dialogue text, resolves voice_id from the speaker's sound_prefix, calls TTS generation, base64-encodes the OGG audio, and publishes `tts.audio`. Falls back to `dialogue.display` when TTS is unavailable or fails.

## ADDED Requirements

### Requirement: TTS engine injection into event handlers

The event handler module SHALL expose `set_tts_engine(engine)` to inject a TTS engine instance (either `TTSEngine` or `TTSRemoteClient`). When set, the dispatch logic SHALL attempt TTS generation. When not set (None), the dispatch SHALL always publish `dialogue.display` (text-only).

#### Scenario: TTS engine injected at startup

- **WHEN** `set_tts_engine(engine)` is called during lifespan with a valid `TTSRemoteClient`
- **THEN** subsequent dialogue dispatches SHALL attempt TTS audio generation

#### Scenario: No TTS engine injected

- **WHEN** `set_tts_engine()` is never called (or called with None)
- **THEN** all dialogue dispatches SHALL publish `dialogue.display` only

### Requirement: Voice ID resolved from speaker's sound_prefix

The dispatch logic SHALL resolve `voice_id` for the chosen speaker by looking up the speaker's `sound_prefix` field from the `candidates` list using the `speaker_id` returned by the conversation manager. The `sound_prefix` (e.g. `"stalker_1"`, `"bandit_3"`) maps directly to pocket_tts voice file stems.

#### Scenario: Speaker found in candidates with sound_prefix

- **WHEN** `speaker_id` is `"5"` and candidates contains `{game_id: "5", sound_prefix: "dolg_1", ...}`
- **THEN** `voice_id` SHALL be `"dolg_1"`

#### Scenario: Speaker has no sound_prefix

- **WHEN** the matched candidate has `sound_prefix: null` or `sound_prefix: ""`
- **THEN** `voice_id` SHALL be `""` (empty string)
- **AND** the TTS engine's fallback voice logic SHALL handle resolution

#### Scenario: Speaker not found in candidates (LLM changed speaker)

- **WHEN** the LLM's `[SPEAKER: id]` parse selects a different candidate than candidates[0]
- **THEN** the dispatch SHALL search all candidates for the matching `game_id`
- **AND** use that candidate's `sound_prefix` as `voice_id`

### Requirement: Conditional TTS-or-text dispatch

After generating dialogue text, the dispatch logic SHALL:
1. If `tts_engine` is set: call `tts_engine.generate_audio(text, voice_id)`
2. If audio generation succeeds: base64-encode the OGG bytes and publish `tts.audio`
3. If audio generation fails or returns None: fall back to `dialogue.display`
4. If `tts_engine` is not set: publish `dialogue.display`

#### Scenario: Successful TTS dispatch

- **WHEN** dialogue `"Stay sharp."` is generated for speaker `"5"` with voice `"dolg_1"`
- **AND** `tts_engine.generate_audio("Stay sharp.", "dolg_1")` returns `(ogg_bytes, 2400)`
- **THEN** `tts.audio` SHALL be published with `speaker_id`, `audio_b64`, `voice_id`, `dialogue`, and `dialogue_id`

#### Scenario: TTS generation returns None

- **WHEN** `tts_engine.generate_audio()` returns `None`
- **THEN** `dialogue.display` SHALL be published with the text payload
- **AND** a warning SHALL be logged

#### Scenario: TTS generation raises exception

- **WHEN** `tts_engine.generate_audio()` raises an exception
- **THEN** `dialogue.display` SHALL be published as fallback
- **AND** the exception SHALL be logged with traceback

#### Scenario: No TTS engine available

- **WHEN** `_tts_engine` is None
- **THEN** `dialogue.display` SHALL be published
- **AND** no TTS generation SHALL be attempted

### Requirement: Monotonic dialogue_id generation

The event handler module SHALL maintain a module-level monotonic counter for `dialogue_id`. Each call to the dispatch function SHALL increment the counter and include it in both `tts.audio` and `dialogue.display` payloads.

#### Scenario: Sequential dialogue IDs across dispatches

- **WHEN** three consecutive dialogues are dispatched
- **THEN** they SHALL receive `dialogue_id` values 1, 2, 3

#### Scenario: dialogue_id included in tts.audio payload

- **WHEN** `tts.audio` is published with `dialogue_id=5`
- **THEN** the payload SHALL contain `"dialogue_id": 5`

### Requirement: TTS engine wired in __main__.py lifespan

`__main__.py` SHALL call `event_handlers.set_tts_engine(tts_engine)` after TTS engine initialization, using the same `tts_engine` instance (which may be `TTSRemoteClient`, `TTSEngine`, or `None`).

#### Scenario: Remote TTS client injected

- **WHEN** `TTS_SERVICE_URL` is set and `TTSRemoteClient` is created
- **THEN** `event_handlers.set_tts_engine(tts_engine)` SHALL be called with the remote client

#### Scenario: No TTS available

- **WHEN** TTS is disabled or initialization fails
- **THEN** `event_handlers.set_tts_engine(None)` SHALL be called (or the call is skipped, leaving the default None)
