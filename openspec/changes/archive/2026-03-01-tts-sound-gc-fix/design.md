## Context

TTS audio plays on NPCs via `sound_object:play_at_pos()` with a per-frame tracking loop (`CreateTimeEvent`) that updates the position to follow the NPC. The `sound_object` (a luabind-wrapped C++ instance) is currently returned by `play_on_npc()` but **discarded by the caller** (`talker_ws_command_handlers.script` line 155 — fire-and-forget). The only remaining reference lives inside the `CreateTimeEvent` closure.

Lua GC can collect any object with zero strong references outside closures. When the luabind userdata is collected its C++ destructor calls `sound_object::stop()`, terminating playback mid-sentence. The bug is probabilistic: shorter clips may survive long enough but longer clips (>100 KB OGG, ~30+ seconds) consistently truncate because the large base64 decode allocations (148 KB string temporaries) spike GC pressure.

Evidence: D#25 (Fanatic backstory) — 144 chunks, 111,056 bytes, ~36 s — server confirmed full generation. Game log showed tracking loop reported "sound finished" after very few ticks, yet player only heard ~8-10 s. The game's own `ph_sound.script` stores `self.played_sound` on a persistent class instance, confirming the pattern.

## Goals / Non-Goals

**Goals:**
- Prevent `sound_object` GC during playback by holding a persistent strong reference
- Release the reference cleanly when playback naturally completes or the NPC despawns
- Add diagnostic tick counting to the tracking loop so truncation issues are immediately visible in logs
- Keep the fix entirely within `tts_slot.lua` (no API changes, no wire protocol changes)

**Non-Goals:**
- Integrating `ogg_patcher.py` (X-Ray spatial metadata injection) — separate concern
- Changing the two-phase processing in `talker_ws_command_handlers.script` — Phase 2 caller is fine, it just shouldn't need to hold the reference
- Queueing or serializing playback — concurrent independent playback must continue working
- Exposing `active_sounds` to external callers for management

## Decisions

### D1: Module-level `active_sounds` table in `tts_slot.lua`

**Choice**: Add `local active_sounds = {}` keyed by `slot_num`. `play_on_npc()` stores `active_sounds[slot_num] = snd` before returning. `start_tracking()` sets `active_sounds[slot_num] = nil` when the loop self-removes.

**Rationale**: Module-level tables are never GC'd (they're reachable from `package.loaded`). Keying by slot number naturally handles reuse — when a slot is reallocated, the old reference is overwritten, which is correct because at that point the old sound should have finished (100-slot gap from `snd_restart`). This is the same proven pattern used by `ph_sound.script` (persistent instance field).

**Alternatives considered**:
- *Caller (command handler) holds the reference*: Would work but scatters TTS lifecycle logic across two files. The slot module already owns allocation, writing, playing, and tracking — it should own the reference too.
- *Global registry outside the module*: Adds unnecessary indirection with no benefit. Module-level state is already the Lua pattern for singleton services.
- *Weak table*: Defeats the purpose — weak references don't prevent GC.

### D2: Tick counter in tracking closure

**Choice**: Add a local `ticks = 0` variable inside `start_tracking()`. Increment on each callback invocation. Log tick count when the loop self-removes.

**Rationale**: If GC truncation recurs despite the fix, tick count immediately reveals the problem: 1-3 ticks = GC (should not happen post-fix), hundreds of ticks = natural completion (~60 FPS × duration), 10-30 ticks = possible engine issue. Zero runtime cost (one integer increment per frame, one log line on removal). This is purely diagnostic and doesn't affect behavior.

### D3: Reference stored before `play_at_pos()` / `play()`

**Choice**: Store `active_sounds[slot_num] = snd` in `play_on_npc()` immediately after `create_sound_object()`, before calling `play_at_pos()` or `play()`.

**Rationale**: Ensures the reference exists before any GC-triggering allocation can happen during playback setup. Even though GC between `create_sound_object()` and `play_at_pos()` is unlikely, defensive ordering costs nothing.

### D4: Release on both tracking exit paths

**Choice**: Clear `active_sounds[slot_num] = nil` when the tracking loop returns true for any reason (`snd:playing() == false` or NPC position is nil). For 2D fallback (no tracking loop), do not store in `active_sounds` — the 2D `snd:play()` call keeps a strong reference internally in X-Ray.

**Update**: Actually 2D playback has the same GC risk. Store the reference for both 3D and 2D paths. For 2D (no tracking loop), start a simplified polling loop that just checks `snd:playing()` and clears the reference when done.

## Risks / Trade-offs

**[Risk] Memory leak if tracking loop never fires** → Mitigation: `CreateTimeEvent` with `delay=0` is guaranteed to fire next frame. The only scenario where it wouldn't is if the game crashes — at which point memory is freed anyway. Slot reuse (after 200 allocations) naturally overwrites orphaned references.

**[Risk] snd_restart at slot 100/200 invalidates active sounds** → Pre-existing issue. The 100-slot gap between flush and reuse makes this extremely unlikely. Not in scope for this fix.

**[Risk] Tick logging adds log noise** → Mitigation: Uses `log.debug` level, only fires once per completed playback. At typical MCM log settings (info+), this won't appear unless the user explicitly enables debug logging.
