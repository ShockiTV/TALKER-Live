## Why

NPC dialogue audio currently plays as flat, non-spatialized desktop audio through the talker_bridge service. The game engine supports 3D spatial audio attached to NPCs via `sound_object:play(npc)`, which would make NPC speech feel immersive — dialogue volume and panning would change as the player moves relative to the speaker. The TTS engine (`TTSRemoteClient`) is already initialized in `talker_service` and the Lua-side slot manager + command handler are already built, but nobody calls `generate_audio()` in the dialogue pipeline.

## What Changes

- Wire TTS audio generation into the dialogue dispatch in `events.py`: after generating dialogue text, call `tts_engine.generate_audio(text, voice_id)`, base64-encode the OGG result, and publish `tts.audio` instead of `dialogue.display`
- Inject `tts_engine` into event handlers via a `set_tts_engine()` setter (same pattern as `set_publisher()`)
- Resolve `voice_id` from the chosen speaker's `sound_prefix` field (already present in candidates data)
- Generate a monotonic `dialogue_id` for logging correlation between Python and Lua
- Fall back to text-only `dialogue.display` when TTS is unavailable or generation fails

## Capabilities

### New Capabilities
- `tts-dialogue-dispatch`: Conditional TTS-or-text dispatch logic in the event handler — calls `generate_audio()`, base64-encodes OGG, publishes `tts.audio` with voice_id resolved from speaker's sound_prefix, falls back to `dialogue.display` on failure

### Modified Capabilities
- `service-tts-generation`: TTS engine injection into event handlers (currently only initialized, never called from the dialogue pipeline)

## Impact

- `talker_service/src/talker_service/handlers/events.py` — new `set_tts_engine()`, dispatch branch (~20 lines)
- `talker_service/src/talker_service/__main__.py` — one injection line: `event_handlers.set_tts_engine(tts_engine)`
- `talker_service/tests/` — new tests for TTS dispatch and text-only fallback
- No Lua changes needed — `handle_tts_audio` and `tts_slot.lua` are already complete
- No new dependencies — `base64` is stdlib, `TTSRemoteClient`/`TTSEngine` already exist
