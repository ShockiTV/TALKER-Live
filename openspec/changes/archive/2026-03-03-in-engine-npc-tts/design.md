## Context

NPC dialogue audio currently flows: Python service generates dialogue text → Lua receives via WS:5557 → Lua publishes `tts.speak` to mic_python via WS:5558 → mic_python runs pocket_tts → streams to desktop speakers via sounddevice → signals `tts.started`/`tts.done` back to Lua.

This produces flat, non-spatialized audio and requires mic_python to run on the same machine as the game. The spike testing confirmed:

- `sound_object:play(npc, 0, s3d)` attaches audio to NPC → 3D spatial, follows movement
- X-Ray engine indexes files at startup only — no runtime file discovery
- Engine caches OGG content on first play (not startup) — writing to un-played slots works
- `snd_restart` console command flushes all caches (causes stutter)
- `io.open("wb")` works at runtime through MO2 USVFS

### Constraints

- STALKER Lua sandbox: no `os.remove`, limited stdlib. `io.open` works for binary read/write.
- Anomaly's `aaa_sound_object_patch.script` wraps `sound_object` with GC-prevention cache (`soundCache` table). All `sound_object()` calls go through this wrapper.
- MO2 USVFS merges mod files at runtime. Writes from Lua go to the MO2 overwrite directory or mod directory — not the base game folder. Silent slot files must be shipped in the mod.
- pocket_tts generates 24kHz mono float32 audio as numpy chunks via `model.generate_audio_stream()`. Converting to OGG Vorbis requires an encoding step.
- Base64 encoding roughly 4/3x the binary size. A typical 5-second TTS clip at 24kHz mono is ~240KB raw → ~60KB OGG → ~80KB base64. Acceptable for WS:5557 (local or LAN).

## Goals / Non-Goals

**Goals:**
- NPC speech plays as 3D spatialized audio attached to the NPC game object
- Python service generates OGG audio and delivers it to Lua via the existing service channel (WS:5557)
- Slot pool of pre-deployed silent OGG files enables runtime audio playback without engine restart
- TTS queue continues to serialize playback (one NPC speaks at a time)
- mic_python TTS remains functional as an optional fallback for desktop speaker playback

**Non-Goals:**
- Streaming/chunked audio delivery (whole OGG sent at once — keeps complexity low)
- Multiple simultaneous NPC speakers (existing queue behavior preserved)
- Voice cloning or new voice model training
- Lip sync or animation hooks
- Remote/cloud TTS providers (pocket_tts only for now)

## Decisions

### D1: OGG audio sent as base64 over existing WS:5557

**Decision**: Python generates the full OGG file, base64-encodes it, and sends it over the service channel as a `tts.audio` message.

**Alternatives considered**:
- *File path sharing* — Python writes to filesystem, sends path to Lua. Rejected: couples Python to game filesystem, breaks server-hosted deployments.
- *Dedicated binary WS channel* — New WS connection for binary audio frames. Rejected: added complexity, new port, new Lua channel plumbing — all for saving ~33% base64 overhead on small payloads.
- *Chunked/streaming delivery* — Send audio in fragments as generated. Rejected for v1: adds buffering complexity on Lua side and the engine needs a complete OGG file to play. Revisit if latency becomes an issue.

**Rationale**: Single-message delivery is simple, the existing WS router handles it, and 60-80KB payloads are well within WS frame limits. No new infrastructure needed.

### D2: Pre-deployed slot pool with round-robin allocation

**Decision**: Ship 100 silent OGG files (`gamedata/sounds/talker_tts/slot_001.ogg` through `slot_100.ogg`). Lua allocates slots via a round-robin counter. On each `tts.audio` message, Lua writes the OGG bytes to the next slot file, creates a `sound_object` for that path, and calls `play()` on it.

**Alternatives considered**:
- *Fewer slots (10-20)* — Risk: if playback is slow or audio overlaps in edge cases, slots run out. 100 slots at ~1KB each is trivial storage (100KB total).
- *Dynamic slot naming* — Generate unique filenames at runtime. Rejected: engine only indexes files at startup, so dynamically-named files would never be found.
- *`snd_restart` after each play* — Frees slots immediately but causes noticeable audio stutter. Rejected as primary strategy.

**Rationale**: 100 slots covers long play sessions (at average 10-15 second dialogue, that's ~17–25 minutes before wrapping). Round-robin is simple and predictable. The engine caches on first play, so each slot works once before it becomes "used" — by the time slot 1 wraps around, the player has been playing for 15+ minutes and the cache entry is stale anyway.

### D3: `snd_restart` as emergency cache flush at pool wrap

**Decision**: When the round-robin counter wraps from slot 100 back to slot 1, issue `exec_console_cmd("snd_restart")` to flush the engine's sound cache. This ensures all 100 slots are fresh for reuse.

**Alternatives considered**:
- *Never flush* — After 100 audio plays, slots that were played will serve stale cached audio. Unacceptable.
- *Flush every N slots (e.g., 50)* — More frequent stutter for less benefit.
- *Track which slots have been played and only reuse un-played ones* — Complex, and eventually all slots get played.

**Rationale**: One stutter every ~100 dialogue lines (15+ minutes of gameplay) is acceptable. The alternative — stale/wrong audio — is not.

### D4: `play(npc, 0, s3d)` for NPC-attached spatial audio

**Decision**: Use `sound_object:play(npc_obj, 0, sound_object.s3d)` to attach the sound source to the NPC game object. The engine updates the sound's 3D position as the NPC moves.

**Alternatives considered**:
- `play_at_pos(npc, pos, 0, s3d)` — Plays at a fixed world position snapshot. Sound doesn't follow the NPC if they walk away. Confirmed in spike testing.
- `play(actor, 0, s2d)` — 2D flat audio on the player's head. Loses all spatial immersion.

**Rationale**: `play()` is the standard API used by all vanilla NPC barks. It keeps the audio source on the NPC regardless of movement.

### D5: pocket_tts integration in talker_service (not mic_python)

**Decision**: Add pocket_tts as a dependency of `talker_service` and run TTS generation there. The dialogue generator calls TTS after generating dialogue text, then publishes `tts.audio` with the OGG payload.

**Alternatives considered**:
- *Keep TTS in mic_python, relay OGG to talker_service* — Adds a hop (Python→mic_python→Lua) and keeps mic_python as a hard dependency for TTS.
- *Separate TTS microservice* — Over-engineered for local/LAN use.

**Rationale**: talker_service already has the dialogue text and the WS connection to Lua. Adding pocket_tts there is the shortest path. mic_python remains purely for microphone input.

### D6: OGG Vorbis encoding via soundfile

**Decision**: Use the `soundfile` library (libsndfile wrapper) to encode pocket_tts float32 output to OGG Vorbis in memory. Write to a `BytesIO` buffer, then base64-encode.

**Alternatives considered**:
- *PyOgg* — Less maintained, more complex API.
- *ffmpeg subprocess* — External dependency, process overhead per clip.
- *Raw WAV* — Much larger files (~5x), no compression benefit.

**Rationale**: soundfile is well-maintained, supports `format='OGG'`/`subtype='VORBIS'`, works with numpy arrays directly, and can write to file-like objects. One-liner encoding.

### D7: Lua base64 decoding

**Decision**: Implement base64 decode in pure Lua within `bin/lua/infra/` (framework layer). The decoded bytes are written to the slot file via `io.open("wb")`.

**Alternatives considered**:
- *LuaJIT FFI to C base64* — Faster but adds native dependency complexity.
- *Send raw binary over WS* — pollnet's WS implementation may not handle binary frames well; JSON envelope expectations assume text frames.

**Rationale**: Pure Lua base64 decode is simple (~30 lines), TTS payloads are small (60-80KB encoded), and decode is a one-time cost per dialogue line. Performance is not a concern.

### D8: Fire-and-forget playback (no queue)

**Decision**: The `tts.audio` command handler decodes audio, writes to slot, and plays immediately via `play_no_feedback()` — fire-and-forget with no queue, no polling, and no completion tracking. The original plan to rewire the existing TTS queue was dropped during spec refinement because `play_no_feedback()` eliminates the need for playback lifecycle management.

**Alternatives considered**:
- *Rewire existing TTS queue (FIFO, timeout)* — Original plan. Dropped because fire-and-forget playback via `play_no_feedback()` makes queuing unnecessary — the engine handles concurrent sounds natively.
- *Move queue to `bin/lua/domain/service/`* — Better architecture but larger refactor scope and now unnecessary.
- *New dedicated script* — Splits TTS concerns across files unnecessarily.

**Rationale**: Fire-and-forget is the simplest correct approach. The engine's audio system handles overlapping sounds. No completion callback means no `tts.playing`/`tts.done` lifecycle topics are needed on the service channel.

### D9: New WS topics on the service channel

**Decision**: Three new topics on the service channel (WS:5557):

| Topic | Direction | Payload |
|-------|-----------|---------|
| `tts.audio` | Python → Lua | `{ speaker_id, audio_b64, voice_id, dialogue }` |
| `tts.playing` | Lua → Python | `{ speaker_id }` |
| `tts.done` | Lua → Python | `{ speaker_id }` |

- `tts.audio` replaces the old `dialogue.display` + `tts.speak` two-step with a single message that contains both dialogue text and audio.
- `tts.playing` replaces `tts.started` (renamed for clarity — "playing" means audio is actually playing in-engine, not just "started generating").
- `tts.done` semantics unchanged.

**Alternatives considered**:
- *Extend `dialogue.display` payload with optional `audio_b64`* — Tempting, but mixes concerns. `dialogue.display` already has its own handler; adding giant base64 blobs to it muddies the interface.
- *Keep using mic channel topics* — Confusing since mic_python is no longer involved.

**Rationale**: Clean separation. Python publishes `tts.audio` when TTS is enabled; falls back to `dialogue.display` when TTS is disabled. Lua subscribes to both on the service channel.

## Risks / Trade-offs

**[Risk] OGG files persist in MO2 overwrite after session** → Slots are overwritten each session. Not a data leak risk, just disk clutter. Could add cleanup on game exit if needed.

**[Risk] `snd_restart` stutter at slot 100 wrap** → Noticeable but brief (~0.5s). Occurs every 15-25 minutes of active dialogue. Acceptable for v1. Future: investigate per-sound cache invalidation APIs or larger slot pools.

**[Risk] pocket_tts is a heavy dependency (~500MB+ with model)** → Users who don't want TTS can skip it. Make pocket_tts an optional dependency — talker_service works without it, just skips audio generation.

**[Risk] Base64 payload size for long dialogue** → A 30-second clip would be ~500KB base64. The WS frame limit is typically 1MB+. Not a practical concern for dialogue-length audio.

**[Risk] `play(npc)` on dead/despawned NPC** → Engine may crash or no-op. Lua must check `engine.is_alive(npc_obj)` before calling `play()`. Fallback to `play(actor, 0, s2d)` for 2D if NPC is gone.

**[Risk] Multiple dialogue lines queued while one plays** → Fire-and-forget playback via `play_no_feedback()` means the engine handles overlapping sounds natively. No explicit queue needed on the Lua side.
