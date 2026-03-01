## Context

The TTS slot playback system writes OGG audio to 200 pre-deployed slot files and plays them via X-Ray's `sound_object`. X-Ray caches sound resources by path internally. When a player loads a save, the engine retains cached audio from the previous session — meaning `sound_object("slot_N")` may serve stale audio data from slot files written during an earlier save, not the freshly-written content. This causes persistent text/audio mismatch that is invisible from logs (both sides think they sent the right data).

Additionally, within a single session, the file write and `sound_object` creation happen in the same Lua frame. X-Ray may not pick up filesystem changes within the same engine tick.

## Goals / Non-Goals

**Goals:**
- Eliminate stale sound cache desync on save load by flushing X-Ray's cache at game load time
- Ensure file writes are reflected before playback by deferring `sound_object` creation by at least one engine frame
- Preserve concurrent NPC speech — multiple NPCs must be able to talk simultaneously for 3D spatial audio immersion

**Non-Goals:**
- Serializing/queueing TTS playback (destroys immersion of overlapping NPC conversations)
- Changing the Python-side TTS pipeline or wire format
- Addressing network latency or out-of-order WebSocket delivery

## Decisions

**1. `snd_restart` on `on_game_load` (not lazy/first-use)**
- *Choice*: Issue `snd_restart` eagerly in the `on_game_load` callback, before any TTS allocation
- *Alternative*: Lazy `snd_restart` on first `allocate()` call — rejected because it runs during gameplay interaction, causing a perceptible audio stutter at an unpredictable moment
- *Rationale*: `on_game_load` fires while the loading screen is still visible, so the cache flush is invisible to the player

**2. Two-phase write→play with per-message `CreateTimeEvent(delay=0)`**
- *Choice*: Phase 1 writes OGG immediately; Phase 2 defers display+play via `CreateTimeEvent(delay=0)` with a unique key per message
- *Alternative*: Single-phase (write and play in same frame) — rejected because X-Ray may serve cached/stale data
- *Alternative*: Queue-based serialization — rejected because it prevents concurrent NPC speech
- *Rationale*: `delay=0` guarantees at least one engine frame between write and play; unique keys allow multiple deferred plays to coexist independently

**3. Monotonic counter for `CreateTimeEvent` keys**
- *Choice*: Module-level `_tts_play_counter` incremented per message, used as `CreateTimeEvent` action key
- *Rationale*: X-Ray requires unique (event_id, action_id) pairs for concurrent time events; a counter avoids collisions between rapid-fire messages

## Risks / Trade-offs

- **`snd_restart` flushes ALL cached sounds** → Could cause brief silence for other ambient sounds playing at load time. Mitigation: `on_game_load` fires before gameplay begins, so ambient sounds haven't started yet.
- **One-frame defer adds ~16ms latency** → Imperceptible to the player at 60fps. Acceptable trade-off for cache correctness.
- **`audio_duration_ms` in payload is now unused by Lua** → Harmless extra field; may be useful for future diagnostics/logging. No removal needed.
