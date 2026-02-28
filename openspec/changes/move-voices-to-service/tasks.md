## 1. Service Config & Directory

- [x] 1.1 Create `talker_service/voices/` directory (empty, with `.gitkeep`)
- [x] 1.2 Update `talker_service/src/talker_service/config.py`: change `voices_dir` default from `Path("../talker_bridge/voices")` to `Path("./voices")`
- [x] 1.3 Simplify voice loading glob in `talker_service/src/talker_service/tts/engine.py` from `**/*.safetensors` to `*.safetensors` (flat layout)

## 2. Voice Export Tooling

- [x] 2.1 Add `--source-dir` and `--only` CLI arguments to `tools/voice_triage/phase1_triage.py` using argparse
- [x] 2.2 Create `tools/voice_triage/phase3_export.py` that reads source `.ogg` from `voice_staging/raw/<theme>/` and bakes to `talker_service/voices/<theme>.safetensors` via pocket_tts; supports `--only` filter; skips `no_speach` and `story`

## 3. Add Missing GAMMA Voice Themes

- [x] 3.1 Run phase1 triage against Dux Characters Kit for missing themes; cross-referenced XML profiles to confirm 30 themes actually used by NPCs (removed 6 unused: build_1, build_3, dolg_2, freedom_2, monolith_2, zombied_3)
- [x] 3.2 Run phase2 enhance (LUFS normalization at -16 LUFS) on all 30 themes
- [x] 3.3 Run phase3 export to bake all 30 themes into `talker_service/voices/`

## 4. Bridge TTS Dead Code Removal

- [x] 4.1 Remove `TTSQueue` class from `talker_bridge/python/main.py`
- [x] 4.2 Remove `load_voice_cache()`, `play_tts()`, `_run_tts_task()` functions from bridge `main.py`
- [x] 4.3 Remove `tts.speak` from `LOCAL_TOPICS` and its handler in `handle_local_message` in bridge `main.py`
- [x] 4.4 Remove `--tts` CLI flag parsing and related `tts_enabled` variable usage from bridge `main.py`
- [x] 4.5 Remove `tts.started`/`tts.done` publish calls if present in bridge `main.py`
- [x] 4.6 Clean up unused imports (`pocket_tts`, `sounddevice` if only used for TTS) in bridge `main.py`

## 5. Old Export Tooling Removal

- [x] 5.1 Delete `talker_bridge/python/export_voices.py`
- [x] 5.2 Delete root `export_voices.bat`
- [x] 5.3 Delete `talker_bridge/python/denoise_worker.py` if it exists

## 6. Lua Dead Code Removal

- [x] 6.1 Remove `tts.speak` fallback path from `handle_dialogue_display` in `gamedata/scripts/talker_ws_command_handlers.script`
- [x] 6.2 Delete `bin/lua/domain/repo/voices.lua`
- [x] 6.3 Delete `tests/repo/test_voices.lua` (or equivalent test file for voices.lua)
- [x] 6.4 Remove `tts_enabled()` getter from `bin/lua/interface/config.lua`
- [x] 6.5 Remove `enable_tts` from config defaults in `bin/lua/interface/config.lua` if present

## 7. Verification

- [x] 7.1 Run Lua tests (via MCP) to confirm no regressions from dead code removal
- [x] 7.2 Run Python tests (via MCP) to confirm config change and TTS engine still work
- [x] 7.3 Verify `talker_service/voices/` contains all 30 expected `.safetensors` files
- [x] 7.4 Delete `voice_staging/raw/no_speach/` and `voice_staging/raw/story/` directories
