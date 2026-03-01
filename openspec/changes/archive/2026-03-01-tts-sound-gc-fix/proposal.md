## Why

TTS audio playback on NPCs cuts off mid-sentence. Server logs confirm the full OGG is generated (144 chunks, 111 KB, ~36 seconds), but the game-side tracking loop reports "sound finished" well before the audio actually ends. The `sound_object` returned by `play_on_npc()` is only held by the `CreateTimeEvent` closure — no persistent reference exists. When Lua GC collects the luabind userdata wrapper, the C++ destructor stops the sound. Large base64 decode allocations (111 KB → ~148 KB string) likely trigger GC pressure that collects the closure-held `snd` before playback completes.

## What Changes

- Store active `sound_object` references in a module-level `active_sounds` table keyed by slot number, preventing GC from collecting in-flight audio
- Release the reference only when the tracking loop confirms `snd:playing()` returns false (natural completion)
- Add tick counter to the tracking loop to diagnose whether sounds stop after 1-3 ticks (GC) or hundreds of ticks (engine limit)
- Log tick count on tracking loop removal for correlation with playback duration

## Capabilities

### New Capabilities

_(none — this is a fix to existing behavior)_

### Modified Capabilities

- `tts-slot-playback`: Add requirement that `sound_object` references MUST be held in a persistent table for the duration of playback to prevent garbage collection. Add diagnostic tick logging on tracking loop completion.

## Impact

- **Code**: `bin/lua/domain/service/tts_slot.lua` — add `active_sounds` table, update `start_tracking` and `play_on_npc`
- **Tests**: `tests/domain/service/test_tts_slot.lua` — verify persistent reference lifecycle and tick logging
- **Risk**: Low — purely additive (new table + logging). No API changes, no wire protocol changes.
