## 1. Lua: tts_slot flush_cache method

- [x] 1.1 Add `flush_cache()` to `bin/lua/domain/service/tts_slot.lua` — issues `snd_restart` and resets slot counter to 1
- [x] 1.2 Add test for `flush_cache()` in `tests/domain/service/test_tts_slot.lua`

## 2. Lua: on_game_load cache flush

- [x] 2.1 Call `tts_slot.flush_cache()` in `on_game_load` in `gamedata/scripts/talker_ws_command_handlers.script`

## 3. Lua: Two-phase tts.audio handler

- [x] 3.1 Refactor `handle_tts_audio` into Phase 1 (immediate decode+allocate+write) and Phase 2 (deferred display+play via `CreateTimeEvent(delay=0)`)
- [x] 3.2 Add monotonic `_tts_play_counter` for unique `CreateTimeEvent` action keys
- [x] 3.3 Remove any queue/serialization — each message processes independently

## 4. Python: TTS engine duration info

- [x] 4.1 Have `generate_audio` return `(ogg_bytes, duration_ms)` tuple (informational for payload)
- [x] 4.2 Include `audio_duration_ms` in `tts.audio` payload from `_publish_dialogue`
- [x] 4.3 Update Python TTS engine tests for tuple return
- [x] 4.4 Update Python dialogue TTS integration tests for tuple return

## 5. Verification

- [x] 5.1 Run all Lua tests (435 expected)
- [x] 5.2 Run all Python tests (606+ expected, excluding pre-existing test_multi_session failures)
