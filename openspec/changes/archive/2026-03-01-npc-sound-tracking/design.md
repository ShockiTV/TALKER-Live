## Context

TTS audio is currently played via `play_no_feedback(npc, s3d, 0, pos, 1, 1)` inside `tts_slot.play_on_npc()`. This snapshots the NPC's position at play-start and never updates it — if the NPC walks away, the sound stays pinned to the original coordinates.

The Anomaly Radio Extended mod (`ph_sound.script`, shipping in every GAMMA install) proves a working pattern: `play_at_pos()` to start, then a `set_position()` tick loop via `CreateTimeEvent` that follows a game object until `playing()` returns false or the object is invalid.

All changes are contained within `bin/lua/domain/service/tts_slot.lua`. The engine facade already exposes `create_time_event`, `get_position`, and `is_alive` — no new facade methods are needed. `set_position` and `playing` are methods on the `sound_object` instance returned by the engine, not engine globals, so they require no facade wrapper.

## Goals / Non-Goals

**Goals:**
- Audio emitted by an NPC tracks their movement in real-time.
- Automatic cleanup: the tracking loop removes itself when the sound finishes or the NPC becomes invalid.
- Minimal change footprint: only `tts_slot.lua` and its tests are modified.
- 2D fallback path (dead/nil NPC) is unchanged.

**Non-Goals:**
- Replacing `snd_restart` with `getFS():rescan_path()` — worth a separate spike.
- Using `npc:add_sound()` / `npc:play_sound()` — unexplored, much larger surface area.
- Any Python-side changes.
- Adding a stop/cancel API for in-flight sounds (future work if needed).

## Decisions

### D1: Use `play_at_pos` + `set_position` loop (not `play(npc, 0, s3d)`)

Testing showed `snd:play(npc, 0, s3d)` produces no audible sound when the first argument is a non-actor game object. Reason unknown (possibly `aaa_sound_object_patch` interference). `play_at_pos` is proven to work in ph_sound.script and gives us an explicit position we can update.

**Alternative rejected**: `play(npc, 0, s3d)` — silent in prior testing.

### D2: Track via `CreateTimeEvent` returning false/true

The standard X-Ray Lua pattern: a `CreateTimeEvent` callback that returns `false` to keep ticking or `true` to self-remove. The loop calls `snd:set_position(engine.get_position(npc_obj))` each tick (~50 ms engine frame). On stop conditions (not playing, NPC dead/nil), it returns `true`.

**Alternative rejected**: `engine.repeat_until_true` — same mechanism at a higher level but adds indirection without benefit. Direct `create_time_event` mirrors the proven ph_sound.script pattern exactly.

### D3: Tracking loop lives inside `tts_slot.lua`

The new `start_tracking(snd, npc_obj, slot_num)` local function is co-located with `play_on_npc`. It takes the sound object, NPC reference, and slot number (for unique event keying). No external module needs to know about it.

**Alternative considered**: Separate tracking module (`domain/service/sound_tracker.lua`) — overkill for a single function. Can be extracted later if other sound sources need tracking.

### D4: Unique `CreateTimeEvent` keys per active sound

Each tracking event uses `"talker_tts_track"` as the event_id and `"slot_" .. slot_num` as the action_id. Since slot numbers are unique per active playback (round-robin pool, ~200 slots), collisions are impossible during normal operation. If a slot is reused while its previous sound is still playing, the new tracking event replaces the old one naturally.

### D5: No `snd:stop()` on NPC invalidation

If the NPC dies or despawns mid-playback, the tracking loop stops updating position and returns `true` to self-remove. The sound continues playing at its last known position until it naturally finishes. This avoids abrupt audio cut-off on NPC death (a common event — the NPC often speaks about dying).

**Alternative considered**: Call `snd:stop()` when NPC is invalid — rejected because death/despawn callouts should still be audible.

### D6: 2D fallback path is unchanged

When `npc_obj` is nil or dead at play-start, the existing `snd:play(player, 0, S2D)` path remains. No tracking is needed for 2D sounds (they follow the listener automatically).

## Risks / Trade-offs

**[Risk] `set_position` may be called on a sound that has already finished** → The `playing()` check runs first in each tick. If timing causes one extra `set_position` call after the sound ends, X-Ray ignores it silently (observed in ph_sound.script without issues across thousands of GAMMA installs).

**[Risk] Multiple concurrent tracking loops (multiple NPCs speaking)** → Each uses a unique action_id keyed by slot number. `CreateTimeEvent` supports arbitrary concurrent events. No serialization or contention.

**[Risk] NPC moves to a different level (despawn)** → `engine.get_position(npc_obj)` returns nil for despawned objects. The tracking loop checks for nil position and self-removes, leaving the sound at its last valid position.

**[Trade-off] ~50 ms position granularity** → `CreateTimeEvent` ticks at engine frame rate (~20 Hz at 50 ms). This is adequate for NPC walk/run speeds. Higher-frequency tracking is not possible without engine modification and not needed for voice audio.
