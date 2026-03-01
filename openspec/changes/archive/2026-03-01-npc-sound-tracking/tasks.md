## 1. Core Implementation

- [x] 1.1 Add local `start_tracking(snd, npc_obj, slot_num)` function to `tts_slot.lua` that registers a `CreateTimeEvent` (via `engine.create_time_event`) with event_id `"talker_tts_track"` and action_id `"slot_" .. slot_num`. The callback calls `snd:set_position(engine.get_position(npc_obj))` each tick, returning `false` to keep ticking. Returns `true` (self-remove) when `snd:playing()` is false or `engine.get_position(npc_obj)` returns nil.
- [x] 1.2 Replace `play_no_feedback(npc_obj, engine.S3D, 0, pos, 1, 1)` with `play_at_pos(npc_obj, pos, 0, engine.S3D)` in `play_on_npc`.
- [x] 1.3 Call `start_tracking(snd, npc_obj, slot_num)` immediately after `play_at_pos` in the 3D branch.
- [x] 1.4 Update module doc comment to reflect position-tracking playback instead of fire-and-forget.

## 2. Tests

- [x] 2.1 Update test 6 (3D spatial audio) to assert `play_at_pos` is called instead of `play_no_feedback`, and verify `engine.create_time_event` is called with the tracking event_id/action_id.
- [x] 2.2 Update test 7 (2D fallback) to verify NO `create_time_event` is called for the 2D path.
- [x] 2.3 Add test: tracking loop calls `set_position` with updated NPC position and returns `false` to keep ticking.
- [x] 2.4 Add test: tracking loop returns `true` when `playing()` returns false (sound finished).
- [x] 2.5 Add test: tracking loop returns `true` when `get_position(npc_obj)` returns nil (NPC despawned).
