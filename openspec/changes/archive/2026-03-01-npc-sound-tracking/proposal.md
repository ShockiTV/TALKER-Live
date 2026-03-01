## Why

TTS audio played via `play_no_feedback()` takes a one-time position snapshot of the NPC and never updates it. If the NPC moves after speaking begins, the sound stays anchored at the original position — breaking spatial immersion. Switching to `play_at_pos()` with a `set_position()` tracking loop (a proven pattern shipping in every GAMMA install via `ph_sound.script`) makes the audio source follow the NPC in real-time with minimal code change.

## What Changes

- Replace `play_no_feedback(npc, s3d, 0, pos, 1, 1)` with `play_at_pos(npc, pos, 0, s3d)` in `tts_slot.lua`'s `play_on_npc` function.
- Add a position-tracking loop that calls `snd:set_position(npc:position())` every ~50 ms via `CreateTimeEvent` (through the engine facade), stopping when `snd:playing()` returns false or the NPC becomes invalid.
- Expose any new engine facade methods needed (e.g., `get_position`).
- Update existing tests for `play_on_npc` to assert the new `play_at_pos` call and verify the tracking loop lifecycle.

## Capabilities

### New Capabilities

(none — this modifies an existing capability)

### Modified Capabilities

- `tts-slot-playback`: The "Play audio attached to NPC via fire-and-forget" requirement changes from fire-and-forget (`play_no_feedback`) to position-tracking playback (`play_at_pos` + `set_position` loop with automatic cleanup).

## Impact

- **`bin/lua/domain/service/tts_slot.lua`** — Primary change: `play_on_npc` switches playback method and gains a tracking loop.
- **`bin/lua/interface/engine.lua`** — May need new facade methods if `set_position` or `playing()` aren't already exposed.
- **`tests/domain/service/test_tts_slot.lua`** — Tests 6–7 assert `play_no_feedback`; must be updated for `play_at_pos` and tracking behavior.
- **`gamedata/scripts/talker_ws_command_handlers.script`** — No changes expected (it calls `tts_slot.play_on_npc` which encapsulates playback).
- **No Python-side changes** — this is purely Lua/engine-level.
