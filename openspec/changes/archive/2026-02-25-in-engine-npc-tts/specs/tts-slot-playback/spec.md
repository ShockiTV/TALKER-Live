## ADDED Requirements

### Requirement: Silent OGG slot files shipped with mod
The mod SHALL ship 200 silent OGG Vorbis files at `gamedata/sounds/characters_voice/talker_tts/slot_1.ogg` through `slot_200.ogg`. Each file SHALL be a valid OGG Vorbis containing silence (minimum duration to be accepted by X-Ray, e.g. 0.1s at 44100Hz mono). These files exist so the X-Ray engine indexes them at startup.

#### Scenario: Slot files present at game launch
- **WHEN** the game starts with the TALKER mod active
- **THEN** the engine indexes all 200 `characters_voice\talker_tts\slot_N` sound paths
- **AND** `sound_object("characters_voice\\talker_tts\\slot_1")` succeeds without error

#### Scenario: Slot file contains valid OGG silence
- **WHEN** `slot_1.ogg` is opened by the engine
- **THEN** it decodes as valid OGG Vorbis audio containing silence

### Requirement: Round-robin slot allocation
The slot manager SHALL maintain a numeric counter starting at 1. Each call to allocate a slot SHALL return the current counter value and increment it. When the counter exceeds 200, it SHALL wrap to 1.

#### Scenario: Sequential allocation
- **WHEN** three slots are allocated in sequence
- **THEN** the returned slot numbers are 1, 2, 3

#### Scenario: Wrap-around at pool boundary
- **WHEN** the current counter is 200 and a slot is allocated
- **THEN** slot 200 is returned
- **AND** the counter wraps to 1

### Requirement: Write OGG bytes to allocated slot file
When OGG audio bytes are provided for a slot, the slot manager SHALL write the bytes to the corresponding slot file path using `io.open(path, "wb")`. The slot file path SHALL be resolved relative to `$fs_root$` (i.e., `gamedata/sounds/characters_voice/talker_tts/slot_N.ogg`).

#### Scenario: Binary write succeeds
- **WHEN** OGG bytes are written to slot 5
- **THEN** `gamedata/sounds/characters_voice/talker_tts/slot_5.ogg` contains exactly those bytes

#### Scenario: Write failure is logged
- **WHEN** `io.open` returns nil (write failure)
- **THEN** an error is logged and playback for that slot is skipped

### Requirement: Play audio attached to NPC via fire-and-forget
After writing OGG bytes to a slot, the slot manager SHALL create a `sound_object` for that slot path and call `play_no_feedback(npc_obj, sound_object.s3d, 0, pos, 1, 1)` for fire-and-forget 3D spatial audio at the NPC's position. No playback polling or completion detection is performed.

#### Scenario: 3D spatial audio plays on NPC
- **WHEN** slot 5 has been written with TTS audio and the NPC game object is valid and alive
- **THEN** `play_no_feedback(npc_obj, sound_object.s3d, 0, pos, 1, 1)` is called
- **AND** the audio source position is the NPC's current position

#### Scenario: Dead or despawned NPC falls back to 2D
- **WHEN** the NPC game object is nil or not alive
- **THEN** the audio plays as `play(actor, 0, sound_object.s2d)` on the player instead
- **AND** a warning is logged

### Requirement: Base64 decoding in Lua
The command handler SHALL decode base64-encoded strings to raw binary bytes in pure Lua. The decoder SHALL handle standard base64 alphabet (A-Z, a-z, 0-9, +, /) with `=` padding.

#### Scenario: Valid base64 decodes correctly
- **WHEN** a base64 string representing known OGG bytes is decoded
- **THEN** the output matches the original binary bytes exactly

#### Scenario: Empty input returns empty string
- **WHEN** an empty string is decoded
- **THEN** the result is an empty string

### Requirement: Cache flush at interval via snd_restart
Every CACHE_FLUSH_INTERVAL (100) slot allocations, the slot manager SHALL execute `exec_console_cmd("snd_restart")` to flush the engine's sound cache. This fires at slot 100 and slot 200, giving ~100 slots of lead time before those slots are reused with new audio content.

#### Scenario: snd_restart fires at interval boundary
- **WHEN** slot 100 is allocated
- **THEN** `exec_console_cmd("snd_restart")` is called

#### Scenario: snd_restart fires at wrap boundary
- **WHEN** slot 200 is allocated
- **THEN** `exec_console_cmd("snd_restart")` is called

#### Scenario: snd_restart not called during normal allocation
- **WHEN** slot 50 is allocated (not on interval boundary)
- **THEN** `snd_restart` is NOT called

### Requirement: TTS audio command handler
The Lua command handler SHALL subscribe to the `tts.audio` topic on the service channel. On receiving a `tts.audio` message, it SHALL: decode the base64 audio, allocate a slot, write the OGG to the slot file, display the dialogue text, create a dialogue event, and play the audio on the NPC. The handler logs the `dialogue_id` from the payload with `[D#N]` prefix for correlation with the Python side.

#### Scenario: Full tts.audio flow
- **WHEN** `tts.audio` arrives with `{ speaker_id: "5", audio_b64: "<base64>", dialogue: "Stay sharp.", dialogue_id: 3 }`
- **THEN** the audio is decoded, written to the next slot, displayed as dialogue, played on speaker 5's NPC object
- **AND** `[D#3] slot=N speaker=5 dialogue='Stay sharp.'` is logged

#### Scenario: TTS audio with missing NPC object
- **WHEN** `tts.audio` arrives but the NPC game object for `speaker_id` cannot be found
- **THEN** audio plays as 2D on the player actor and a warning is logged

#### Scenario: Missing required fields
- **WHEN** `tts.audio` arrives without `speaker_id`, `audio_b64`, or `dialogue`
- **THEN** an error is logged and processing is skipped
