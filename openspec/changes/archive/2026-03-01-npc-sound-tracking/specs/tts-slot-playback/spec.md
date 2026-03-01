## MODIFIED Requirements

### Requirement: Play audio attached to NPC via fire-and-forget
After writing OGG bytes to a slot, the slot manager SHALL create a `sound_object` for that slot path and call `play_at_pos(npc_obj, pos, 0, sound_object.s3d)` for 3D spatial audio starting at the NPC's position. The slot manager SHALL then start a position-tracking loop that calls `snd:set_position(npc_position)` each engine tick via `CreateTimeEvent` (through the engine facade). The loop SHALL self-remove when `snd:playing()` returns false or the NPC becomes invalid (nil position or not alive).

#### Scenario: 3D spatial audio plays on NPC and tracks movement
- **WHEN** slot 5 has been written with TTS audio and the NPC game object is valid and alive
- **THEN** `play_at_pos(npc_obj, pos, 0, sound_object.s3d)` is called with the NPC's current position
- **AND** a tracking loop is started via `engine.create_time_event` that updates `snd:set_position()` each tick

#### Scenario: Tracking loop follows NPC movement
- **WHEN** the NPC moves while audio is playing
- **THEN** `snd:set_position(engine.get_position(npc_obj))` is called each engine tick
- **AND** the audio source position follows the NPC in real-time

#### Scenario: Tracking loop self-removes when sound finishes
- **WHEN** `snd:playing()` returns false (audio finished)
- **THEN** the tracking loop callback returns true to remove the `CreateTimeEvent`

#### Scenario: Tracking loop self-removes when NPC becomes invalid
- **WHEN** `engine.get_position(npc_obj)` returns nil (NPC despawned or invalid)
- **THEN** the tracking loop callback returns true to remove the `CreateTimeEvent`
- **AND** the sound continues playing at its last known position until it naturally finishes

#### Scenario: Dead or despawned NPC falls back to 2D
- **WHEN** the NPC game object is nil or not alive at play-start
- **THEN** the audio plays as `play(actor, 0, sound_object.s2d)` on the player instead
- **AND** no tracking loop is started
- **AND** a warning is logged

#### Scenario: Concurrent tracking loops are independent
- **WHEN** two slots are playing on different NPCs simultaneously
- **THEN** each has its own tracking loop with a unique `CreateTimeEvent` action_id keyed by slot number
- **AND** neither loop interferes with the other

#### Scenario: Slot reuse replaces previous tracking
- **WHEN** a new sound is played on a slot whose previous sound is still playing
- **THEN** the new `CreateTimeEvent` with the same action_id replaces the old tracking loop
