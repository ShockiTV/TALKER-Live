## Why

On deployed servers, loading a save (or reloading after death) preserves X-Ray engine's internal sound cache from the previous session. TTS slot files written during the earlier session remain cached, so `sound_object` serves stale audio instead of freshly-written content. This causes a persistent text/audio content mismatch — the displayed dialogue text is correct but the played audio belongs to a completely different message. The mismatch persists for all subsequent TTS playback until the game is restarted.

## What Changes

- Add `flush_cache()` to `tts_slot` module that issues `snd_restart` and resets the slot counter
- Call `flush_cache()` in `on_game_load` (fires every time a save is loaded) to purge stale cached slot audio before any TTS playback occurs
- Split `handle_tts_audio` into two phases: immediate file write (decode + allocate + write OGG) followed by deferred display + play (via `CreateTimeEvent(delay=0)`) to guarantee at least one engine frame between filesystem write and `sound_object` creation
- Each TTS message is independent — multiple NPCs can speak simultaneously for natural 3D spatial audio immersion (no serialization/queue)

## Capabilities

### New Capabilities

### Modified Capabilities
- `tts-slot-playback`: Add `flush_cache()` on game load and two-phase write→play processing to prevent X-Ray sound cache desync

## Impact

- **Lua**: `bin/lua/domain/service/tts_slot.lua` (new `flush_cache()` method), `gamedata/scripts/talker_ws_command_handlers.script` (two-phase handler, `on_game_load` flush)
- **Python**: `talker_service/src/talker_service/tts/engine.py` returns `(bytes, duration_ms)` tuple (informational, not consumed by Lua), `talker_service/src/talker_service/dialogue/generator.py` includes `audio_duration_ms` in payload
- **Tests**: Updated `test_tts_slot.lua` (flush_cache test), updated Python TTS integration/unit tests for tuple return
