## 1. Silent OGG Slot Files

- [x] 1.1 Create a Python script to generate 100 silent OGG Vorbis files (24kHz mono, 0.1s) and write them to `gamedata/sounds/talker_tts/slot_001.ogg` through `slot_100.ogg`
- [x] 1.2 Run the script and commit the 100 generated slot files into the mod

## 2. Lua Base64 Decoder

- [x] 2.1 Implement pure-Lua base64 decode function in `bin/lua/infra/base64.lua` (standard alphabet, `=` padding, returns raw binary string)
- [x] 2.2 Write tests for base64 decode: valid input, empty input, padding variations, known OGG header bytes round-trip

## 3. Lua Slot Manager

- [x] 3.1 Create `bin/lua/domain/service/tts_slot.lua` with round-robin counter (1–100), `allocate()` returns slot number and increments, wraps at 100→1
- [x] 3.2 Add `write_slot(slot_num, ogg_bytes)` — resolves slot file path, calls `io.open(path, "wb")`, writes bytes, logs errors
- [x] 3.3 Add `play_on_npc(slot_num, npc_obj)` — creates `sound_object`, calls `play(npc, 0, s3d)`; falls back to `play(actor, 0, s2d)` if NPC nil/dead
- [x] 3.4 Add `is_playing(snd)` polling helper and playback completion callback mechanism (time event that checks `playing()` and fires callback when done)
- [x] 3.5 Add `snd_restart` trigger — call `engine.exec_console_cmd("snd_restart")` when counter wraps from 100→1
- [x] 3.6 Write tests for slot manager: allocation sequence, wrap-around, snd_restart fires on wrap only, write delegates to io.open, play falls back to 2D when NPC is nil

## 4. Lua TTS Command Handler

- [x] 4.1 Add `tts.audio` handler in `talker_ws_command_handlers.script` — decode base64, allocate slot, write OGG, display dialogue text, play audio on NPC (fire-and-forget via `play_no_feedback`, no lifecycle topics needed)
- [x] ~~4.2 Add playback completion callback that publishes `tts.done` and processes next queue item~~ — Dropped: fire-and-forget playback via `play_no_feedback()` eliminates need for completion tracking
- [x] ~~4.3 Rewire TTS queue: replace `TTS_QUEUE_MAX` with uncapped FIFO~~ — Dropped: `play_no_feedback()` is fire-and-forget, no queue needed
- [x] 4.4 Register `tts.audio` topic subscription in `talker_ws_command_handlers.script` via `register_command_handler()`

## 5. Python TTS Module

- [x] 5.1 Create `talker_service/src/talker_service/tts/__init__.py` with optional pocket_tts import guard (ImportError → log warning, set `TTS_AVAILABLE = False`)
- [x] 5.2 Create `talker_service/src/talker_service/tts/engine.py` with `TTSEngine` class — `load(voices_dir)` loads pocket_tts model + voice cache from `.safetensors` files
- [x] 5.3 Add `TTSEngine.generate_audio(text, voice_id) -> bytes | None` — runs pocket_tts inference, concatenates float32 chunks, encodes to OGG Vorbis via soundfile BytesIO, returns OGG bytes
- [x] 5.4 Add voice_id resolution: lookup voice_id in cache, fall back to first available voice if not found, return None if cache empty
- [x] 5.5 Wire `generate_audio` to run via `run_in_executor` so it doesn't block the asyncio event loop
- [x] 5.6 Write tests for TTSEngine: optional import guard, voice cache loading, OGG generation mock, voice_id fallback, empty text returns None

## 6. Python Dialogue→TTS Integration

- [x] 6.1 Add base64 encoding step in dialogue publisher: after generating OGG bytes, base64-encode and publish `tts.audio` with `speaker_id`, `audio_b64`, `voice_id`, `dialogue`
- [x] 6.2 Add fallback logic: if TTS unavailable or generation fails, publish `dialogue.display` instead (existing behavior)
- [x] 6.3 ~~Add `tts.playing` and `tts.done` topic handlers in ws_router~~ — Dropped: fire-and-forget playback means no lifecycle topics on the service channel
- [x] 6.4 Add TTS configuration: `tts_enabled` flag, `voices_dir` path in service config (pydantic-settings)
- [x] 6.5 Initialize TTSEngine at service startup (in `__main__.py` lifespan) when `tts_enabled` is true
- [x] 6.6 Write tests for dialogue→TTS flow: TTS enabled publishes tts.audio, TTS disabled publishes dialogue.display, generation failure falls back

## 7. Python Dependencies

- [x] 7.1 Add `pocket_tts` and `soundfile` as optional dependencies in `pyproject.toml` (extras group `[tts]`)
- [x] 7.2 Update `requirements.txt` with the new optional deps commented or in a separate section

## 8. WS API Documentation

- [x] 8.1 Add `tts.audio` topic (Python→Lua) to `docs/ws-api.yaml` with full payload schema
- [x] ~~8.2 Add `tts.playing` and `tts.done` topics (Lua→Python) to `docs/ws-api.yaml`~~ — Dropped: no lifecycle topics on the service channel (mic channel `tts.started`/`tts.done` already documented)

## 9. mic_python Fallback Path

- [x] 9.1 Update dialogue publisher to only send `tts.speak` to mic channel when in-engine TTS is NOT active (pocket_tts not loaded or voice unavailable)
- [x] 9.2 Verify mic_python `tts.speak` handler still works when in-engine TTS is disabled — no regressions
