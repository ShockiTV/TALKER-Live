## 1. Core Fix — Persistent Sound References

- [x] 1.1 Add `local active_sounds = {}` module-level table to `tts_slot.lua`
- [x] 1.2 Store `active_sounds[slot_num] = snd` in `play_on_npc()` immediately after `create_sound_object()`, before `play_at_pos()`/`play()` calls
- [x] 1.3 Clear `active_sounds[slot_num] = nil` in `start_tracking()` on both exit paths (sound finished, NPC invalid)

## 2. 2D Fallback Tracking

- [x] 2.1 Add a simplified polling loop for the 2D fallback path that checks `snd:playing()` and clears `active_sounds[slot_num]` when done
- [x] 2.2 Include tick counter in the 2D polling loop matching the 3D tracking pattern

## 3. Diagnostic Tick Counter

- [x] 3.1 Add `local ticks = 0` in `start_tracking()` closure, increment each callback
- [x] 3.2 Log tick count at `log.debug` level on tracking loop removal (both exit paths)

## 4. Cache Flush Update

- [x] 4.1 Clear `active_sounds` table in `flush_cache()` (set to `{}` or iterate-and-nil)

## 5. Testing Helpers

- [x] 5.1 Add `M._get_active_count()` that returns the count of entries in `active_sounds`
- [x] 5.2 Update `M._reset_counter()` to also clear `active_sounds`

## 6. Tests

- [x] 6.1 Test that `play_on_npc()` stores a reference in `active_sounds` (mock engine, check `_get_active_count()`)
- [x] 6.2 Test that tracking loop completion clears the `active_sounds` entry
- [x] 6.3 Test that `flush_cache()` clears `active_sounds`
- [x] 6.4 Test that 2D fallback path also stores a reference in `active_sounds`
- [x] 6.5 Test that concurrent playback on different slots maintains independent `active_sounds` entries
