## 1. Voice Export Tooling

- [x] 1.1 Create `mic_python/voices/` directory (placeholder `.gitkeep`)
- [x] 1.2 Create `mic_python/python/export_voices.py` — iterates `voices/*.wav`, calls `TTSModel.load_model()` + `get_state_for_audio_prompt()` + `export_model_state()`, skips existing `.safetensors`, logs results
- [x] 1.3 Create `export_voices.bat` in repo root — activates `mic_python/.venv`, runs `export_voices.py`, pauses on completion
- [x] 1.4 Add `pocket-tts` to `mic_python/requirements.txt`

## 2. mic_python TTS Engine

- [x] 2.1 Add `--tts` flag to argument parser in `mic_python/python/main.py`
- [x] 2.2 Add `load_voice_cache(voices_dir)` function — loads all `*.safetensors` using `TTSModel.get_state_for_audio_prompt()` into `dict[str, voice_state]` at startup when `--tts` is active
- [x] 2.3 Add `play_tts(text, voice_state)` function — opens `sd.OutputStream(samplerate=24000, channels=1, dtype='float32')`, iterates `generate_audio_stream()` chunks, writes each to stream
- [x] 2.4 Introduce `TaskQueue` (FIFO deque) and `state` machine in `main.py` — states: `IDLE`, `TTS_ACTIVE`, `STT_ACTIVE`; `mic.start` and `tts.speak` enqueue when not IDLE, process next on task completion
- [x] 2.5 Add `tts.speak` message handler — extracts `voice_id`, `text`, `speaker_id`; looks up voice in cache (fallback to first available); publishes `tts.started`; calls `play_tts()`; publishes `tts.done`
- [x] 2.6 Add `tts.` to ZMQ subscription filter in `main.py` when `--tts` is active
- [x] 2.7 Refactor existing `mic.start` / `mic.stop` handlers to use the shared task queue

## 3. launch_mic.bat TTS Options

- [x] 3.1 Add two new menu entries in `launch_mic.bat` — "Whisper API with TTS" and "Whisper Local with TTS" — that append `--tts` to the python launch command
- [x] 3.2 Update the venv setup label to install from `requirements.txt` (already does this — verify `pocket-tts` is picked up)

## 4. ~~Lua Voice Data Table~~ (Superseded)

> Removed during implementation. NPCs use their engine-assigned voice theme
> (`npc:sound_prefix()`) directly — no faction-pool fallback needed.

- [x] ~4.1 Create `bin/lua/domain/data/voice_data.lua`~ — **Deleted**: voice_id is resolved at runtime via `engine.get_sound_prefix()`

## 5. ~~Lua Voice Repository~~ (Superseded)

> Removed during implementation. No Lua-side voice cache or persistence needed;
> `voice_id` is fetched on-demand at `tts.speak` time.

- [x] ~5.1 Create `bin/lua/domain/repo/voices.lua`~ — **Deleted**
- [x] ~5.2 Add `set_voice` / `get_all_voices` / `set_all_voices`~ — **Deleted**
- [x] ~5.3 Write Lua unit tests for `voices.lua`~ — **Deleted**

## 6. ~~Lua Character Model (voice_id)~~ (Superseded)

> Removed during implementation. `voice_id` is not a character property;
> it is resolved from the engine at `tts.speak` dispatch time.

- [x] ~6.1 Add `voice_id` field to `Character.new()`~ — **Removed from character.lua**
- [x] ~6.2 Update `Character.new()` unit tests~ — **voice_id tests removed**

## 7. ~~Lua ZMQ Serialisation (voice_id)~~ (Superseded)

> Removed during implementation. `voice_id` is not part of the character wire
> format; it is resolved in Lua and sent directly in `tts.speak` payload.

- [x] ~7.1 Add `voice_id` to `serialize_character()`~ — **Removed from serializer.lua**
- [x] ~7.2 Update serialiser tests~ — **voice_id tests removed**

## 8. ~~Lua Persistence (voices)~~ (Superseded)

> Removed during implementation. Voice assignment is stateless (engine lookup),
> so no save/load is needed.

- [x] ~8.1 Add `voices_data` save/load in persistence script~ — **Removed from talker_game_persistence.script**

## 9. Lua ZMQ Integration — Subscribe to tts.* from mic_python

- [x] 9.1 In `gamedata/scripts/talker_zmq_integration.script`, add subscription to port 5557 for `tts.` topic prefix
- [x] 9.2 Route `tts.started` and `tts.done` messages to `talker_zmq_command_handlers` dispatch table

## 10. Lua TTS Queue and Command Handlers

- [x] 10.1 In `gamedata/scripts/talker_zmq_command_handlers.script`, add `local tts_queue = {}`
- [x] 10.2 Add `publish_next_tts()` helper
- [x] 10.3 Modify `handle_dialogue_display()` — TTS and non-TTS paths
- [x] 10.4 Add `handle_tts_started()`
- [x] 10.5 Add `handle_tts_done()`
- [x] 10.6 Add timeout handler (via `engine.create_time_event`)
- [x] 10.7 Register `tts.started` and `tts.done` in the command dispatch table
- [x] 10.8 Add `config.tts_enabled()` getter in `bin/lua/interface/config.lua` — reads MCM `enable_tts` key (default false)

## 11. Documentation and Cleanup

- [x] 11.1 Document the three new ZMQ topics (`tts.speak`, `tts.started`, `tts.done`) in `docs/zmq-api.yaml`
- [x] 11.2 Add TTS setup section to `docs/Python_Service_Setup.md`
- [x] 11.3 Verify `mic_python/voices/.gitkeep` is committed and voice `.safetensors` files are in `.gitignore`
