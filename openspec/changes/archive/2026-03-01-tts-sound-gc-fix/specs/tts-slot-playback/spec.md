## MODIFIED Requirements

### Requirement: Play audio attached to NPC with position tracking
After writing OGG bytes to a slot, the slot manager SHALL create a `sound_object` for that slot path and call `play_at_pos(npc_obj, pos, 0, sound_object.s3d)` for 3D spatial audio starting at the NPC's position. The slot manager SHALL store a persistent strong reference to the `sound_object` in a module-level `active_sounds` table keyed by slot number, preventing garbage collection of the luabind userdata during playback. The slot manager SHALL then start a position-tracking loop that calls `snd:set_position(npc_position)` each engine tick via `CreateTimeEvent` (through the engine facade). The tracking loop SHALL maintain a tick counter incremented on each callback invocation. The loop SHALL self-remove when `snd:playing()` returns false or the NPC becomes invalid (nil position or not alive). On self-removal, the loop SHALL clear the `active_sounds` entry for that slot and log the tick count at debug level.

#### Scenario: 3D spatial audio plays on NPC and tracks movement
- **WHEN** slot 5 has been written with TTS audio and the NPC game object is valid and alive
- **THEN** `play_at_pos(npc_obj, pos, 0, sound_object.s3d)` is called with the NPC's current position
- **AND** `active_sounds[5]` holds a reference to the `sound_object`
- **AND** a tracking loop is started via `engine.create_time_event` that updates `snd:set_position()` each tick

#### Scenario: Tracking loop follows NPC movement
- **WHEN** the NPC moves while audio is playing
- **THEN** `snd:set_position(engine.get_position(npc_obj))` is called each engine tick
- **AND** the audio source position follows the NPC in real-time

#### Scenario: Tracking loop self-removes when sound finishes
- **WHEN** `snd:playing()` returns false (audio finished)
- **THEN** the tracking loop callback returns true to remove the `CreateTimeEvent`
- **AND** `active_sounds[slot_num]` is set to nil
- **AND** the tick count is logged at debug level

#### Scenario: Tracking loop self-removes when NPC becomes invalid
- **WHEN** `engine.get_position(npc_obj)` returns nil (NPC despawned or invalid)
- **THEN** the tracking loop callback returns true to remove the `CreateTimeEvent`
- **AND** `active_sounds[slot_num]` is set to nil
- **AND** the tick count is logged at debug level

#### Scenario: Dead or despawned NPC falls back to 2D with persistent reference
- **WHEN** the NPC game object is nil or not alive at play-start
- **THEN** the audio plays as `play(actor, 0, sound_object.s2d)` on the player instead
- **AND** `active_sounds[slot_num]` holds a reference to the `sound_object`
- **AND** a simplified polling loop checks `snd:playing()` and clears the reference when done
- **AND** a warning is logged

#### Scenario: Concurrent tracking loops are independent
- **WHEN** two slots are playing on different NPCs simultaneously
- **THEN** each has its own tracking loop with a unique `CreateTimeEvent` action_id keyed by slot number
- **AND** each has its own `active_sounds` entry
- **AND** neither loop interferes with the other

#### Scenario: Slot reuse replaces previous tracking
- **WHEN** a new sound is played on a slot whose previous sound is still playing
- **THEN** the new `CreateTimeEvent` with the same action_id replaces the old tracking loop
- **AND** the new `sound_object` reference overwrites the old `active_sounds` entry

#### Scenario: sound_object survives garbage collection during playback
- **WHEN** a large TTS audio clip is playing (e.g., 100+ KB OGG, 30+ seconds)
- **AND** Lua GC runs during playback
- **THEN** the `sound_object` is NOT collected because `active_sounds` holds a strong reference
- **AND** audio plays to completion without truncation

#### Scenario: Tick count reflects playback duration
- **WHEN** a 10-second clip finishes playing at 60 FPS
- **THEN** the logged tick count is approximately 600
- **AND** a tick count of 1-3 would indicate premature GC collection (diagnostic signal)

### Requirement: Sound cache flush on game load
The slot manager SHALL provide a `flush_cache()` method that executes `snd_restart`, resets the slot counter to 1, and clears all entries from the `active_sounds` table. The command handler SHALL call `flush_cache()` in its `on_game_load` callback so that stale cached audio from a previous save/session is purged before any TTS playback occurs.

#### Scenario: flush_cache resets counter, clears active sounds, and flushes sound cache
- **WHEN** `flush_cache()` is called
- **THEN** `exec_console_cmd("snd_restart")` is executed
- **AND** the slot counter is reset to 1
- **AND** `active_sounds` is cleared (empty table)

#### Scenario: on_game_load triggers flush_cache
- **WHEN** the player loads a save game
- **THEN** `flush_cache()` is called before any TTS slot allocation occurs
- **AND** the cache flush happens while the loading screen is still visible

## ADDED Requirements

### Requirement: Active sounds diagnostic query
The slot manager SHALL expose a `_get_active_count()` function that returns the number of entries in the `active_sounds` table. This is for testing and diagnostic purposes only.

#### Scenario: Active count reflects playing sounds
- **WHEN** two slots are currently playing audio
- **THEN** `_get_active_count()` returns 2

#### Scenario: Active count is zero when idle
- **WHEN** no audio is playing
- **THEN** `_get_active_count()` returns 0
