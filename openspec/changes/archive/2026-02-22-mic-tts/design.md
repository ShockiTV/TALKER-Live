## Context

mic_python currently handles microphone input (record → transcribe → publish result) via a ZMQ loop on ports 5555/5557. It already uses `sounddevice` for audio recording. The talker_service generates AI dialogue text and sends `dialogue.display` to Lua; Lua currently shows HUD text immediately.

Pocket TTS (kyutai-labs) provides voice cloning from a reference audio sample, exporting a 256 kB `.safetensors` kvcache file that loads near-instantly. Audio generation is streaming (`generate_audio_stream`) and yields `float32` numpy-compatible chunks at 24 kHz — directly playable via `sounddevice.OutputStream`.

Characters in Lua already have a `backstory` string assigned on first encounter via `backstories.lua` using the display-name faction. Voice assignment does **not** follow this pattern — each NPC already has an engine-assigned voice theme via `npc:sound_prefix()` (e.g. `"stalker_1"`), which maps directly to a folder in `mic_python/voices/`. The `voice_id` is resolved on-demand at TTS dispatch time, not stored on the character.

## Goals / Non-Goals

**Goals:**
- Audio playback of AI dialogue in mic_python, streamed to default audio output
- Single shared task queue in mic_python ensuring STT and TTS are never concurrent
- Lua HUD text displayed in sync with TTS start, not on dialogue receipt
- Export tooling to bake reference audio into `.safetensors` for fast loading
- TTS is opt-in via `--tts` flag; mic_python startup cost is unchanged when disabled
- Voice ID resolved at runtime from engine's `npc:sound_prefix()` — no Lua persistence needed

**Non-Goals:**
- Voice selection in-game UI (not in this change)
- Multiple simultaneous NPC voices (single queue, serial playback)
- Custom TTS model fine-tuning
- talker_service involvement in TTS — mic_python handles all audio
- Modifying the STALKER game audio engine

## Decisions

### Decision 1: mic_python as TTS host (not talker_service)

**Chosen**: mic_python hosts the TTS model.  
**Alternative considered**: talker_service hosts TTS and sends audio over ZMQ.  
**Rationale**: mic_python is already required for users who want mic input, runs locally on the user's machine (not a remote server), and already has sounddevice. Sending audio over ZMQ would mean transferring 10–100 kB of audio data per line via ZMQ — unnecessary given mic_python is local. talker_service may eventually run remotely; TTS should remain local.

### Decision 2: voice_id resolved at runtime from engine sound_prefix

**Chosen**: `voice_id` is resolved on-demand at `tts.speak` dispatch time via `engine.get_sound_prefix(obj)`, which returns the NPC's engine-assigned voice theme (e.g. `"stalker_1"`). No Lua-side cache, persistence, or faction-pool fallback is needed.  
**Alternative considered (original spec)**: `voices.lua` module with faction-keyed pools, in-memory cache, and save/load persistence.  
**Rationale**: Every NPC already has a unique voice theme assigned by the STALKER engine. Using it directly is simpler, avoids stale caches, removes 3 Lua modules, and eliminates save-data migration concerns. mic_python handles unknown `voice_id` by falling back to the first available voice in its cache.

### Decision 3: Shared STT+TTS task queue in mic_python

**Chosen**: Single task queue with a state machine (IDLE / STT_ACTIVE / TTS_ACTIVE); mic.start and tts.speak both enqueue if not IDLE.  
**Alternative considered**: Separate queues for STT and TTS, interleaved by priority.  
**Rationale**: sounddevice cannot record and play simultaneously without risk of audio feedback. A single IDLE/BUSY model is simpler and correct. STT (player input) is rare; the queue will rarely have depth > 1.

### Decision 4: HUD text shown on tts.started, not on dialogue.display

**Chosen**: Lua withholds HUD display until mic_python publishes `tts.started`.  
**Alternative considered**: Show HUD immediately on `dialogue.display` (current behavior unchanged when TTS disabled).  
**Rationale**: Aligns visual and audio output. Player reads the subtitle as the NPC starts speaking, not seconds before. When TTS is disabled, the existing immediate-display behavior is preserved unchanged.

### Decision 5: Eager voice cache loading at startup

**Chosen**: All `.safetensors` in `voices/` are loaded into a `dict[str, voice_state]` at startup (when `--tts` is active).  
**Alternative considered**: Lazy loading on first use per voice_id.  
**Rationale**: 12 files × 256 kB = ~3 MB. Tensor deserialization is near-instant (no model inference). Eliminates per-dialogue latency spike on first encounter per voice.

### Decision 6: Timeout sentinel for stuck TTS queue

**Chosen**: Lua implements a 30-second timeout after sending `tts.speak`; if `tts.started` is not received, the item is dropped and the queue advances.  
**Rationale**: mic_python crash or slow model startup must not permanently block the Lua dialogue queue.

## Risks / Trade-offs

**[Risk] Pocket TTS model download at first run** → Mitigation: Document in README; `--tts` flag makes it opt-in so non-TTS users are unaffected.

**[Risk] TTS generation latency (CPU)** → Mitigation: `generate_audio_stream` starts playback before full generation completes. On CPU, first chunk arrives in ~1–3 seconds depending on hardware.

**[Risk] Queue depth grows if AI generates dialogue faster than TTS plays it** → Mitigation: Lua queue is length-limited (max 5 items); overflow items are dropped with a log warning.

**[Risk] Voice file missing for an NPC** → Mitigation: mic_python falls back to first available voice in cache if `voice_id` not found.

**[Risk] Simultaneous audio feedback (mic + speaker)** → Mitigation: Shared queue ensures TTS_ACTIVE and STT_ACTIVE never overlap.

## Migration Plan

1. Drop `.wav` files into `mic_python/voices/` (or use provided samples)
2. Run `export_voices.bat` once to bake `.safetensors`
3. Launch `launch_mic.bat` → choose a "with TTS" option
4. No Lua save migration required — voice_id is resolved from the engine at runtime (not persisted)

## Open Questions

- Should `tts.done` carry the dialogue text for logging purposes? (Currently only `speaker_id`)
- Should the Lua TTS queue be persisted across map transitions or reset? (Leaning: reset — in-flight dialogue is always stale after a transition)
