# tts-slot-playback (delta)

## ADDED Requirements

### Requirement: Sound cache flush on game load
The slot manager SHALL provide a `flush_cache()` method that executes `snd_restart` and resets the slot counter to 1. The command handler SHALL call `flush_cache()` in its `on_game_load` callback so that stale cached audio from a previous save/session is purged before any TTS playback occurs.

#### Scenario: flush_cache resets counter and flushes sound cache
- **WHEN** `flush_cache()` is called
- **THEN** `exec_console_cmd("snd_restart")` is executed
- **AND** the slot counter is reset to 1

#### Scenario: on_game_load triggers flush_cache
- **WHEN** the player loads a save game
- **THEN** `flush_cache()` is called before any TTS slot allocation occurs
- **AND** the cache flush happens while the loading screen is still visible

#### Scenario: Slots written in previous session are not served from cache
- **WHEN** a save is loaded after a previous session wrote TTS audio to slot files
- **THEN** `sound_object` for any slot path returns freshly-read data from disk, not stale cached audio

## MODIFIED Requirements

### Requirement: TTS audio command handler
The Lua command handler SHALL subscribe to the `tts.audio` topic on the service channel. On receiving a `tts.audio` message, it SHALL process in two phases:

**Phase 1 (immediate, same frame):** Decode the base64 audio, allocate a slot, and write the OGG to the slot file.

**Phase 2 (deferred, next engine frame):** Display the dialogue text, create a dialogue event, and play the audio on the NPC. Deferral SHALL use `CreateTimeEvent` with `delay=0` and a unique key per message (monotonic counter) to guarantee at least one engine frame between file write and `sound_object` creation.

Each message SHALL be processed independently — multiple NPCs MUST be able to speak simultaneously for 3D spatial audio immersion. There SHALL be no serialization or queueing of TTS playback across messages.

The handler logs the `dialogue_id` from the payload with `[D#N]` prefix for correlation with the Python side.

#### Scenario: Full tts.audio flow with two-phase processing
- **WHEN** `tts.audio` arrives with `{ speaker_id: "5", audio_b64: "<base64>", dialogue: "Stay sharp.", dialogue_id: 3 }`
- **THEN** the audio is decoded and written to the next slot in the current frame
- **AND** display + play is deferred to the next engine frame via `CreateTimeEvent(delay=0)`
- **AND** `[D#3] slot=N speaker=5 dialogue='Stay sharp.'` is logged

#### Scenario: TTS audio with missing NPC object
- **WHEN** `tts.audio` arrives but the NPC game object for `speaker_id` cannot be found
- **THEN** audio plays as 2D on the player actor and a warning is logged

#### Scenario: Missing required fields
- **WHEN** `tts.audio` arrives without `speaker_id`, `audio_b64`, or `dialogue`
- **THEN** an error is logged and processing is skipped

#### Scenario: Write phase failure aborts processing
- **WHEN** Phase 1 (decode/allocate/write) fails
- **THEN** an error is logged and Phase 2 (display/play) is NOT scheduled

#### Scenario: Concurrent NPC speech is not serialized
- **WHEN** two `tts.audio` messages arrive in rapid succession for different speakers
- **THEN** both messages are processed independently (both audio streams play simultaneously)
- **AND** neither message waits for the other to finish
