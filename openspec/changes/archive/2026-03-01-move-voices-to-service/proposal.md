## Why

TTS voice data (`.safetensors` files) currently lives in `talker_bridge/voices/` alongside raw source audio, nested in per-theme subdirectories with game audio subfolders. The `talker_service` is the sole consumer of these files for in-engine 3D TTS generation, yet references them cross-package via `voices_dir = ../talker_bridge/voices`. Meanwhile, the bridge retains dead TTS code (`TTSQueue`, `load_voice_cache`, `play_tts`, `--tts` flag) from the pre-3D era when it did 2D desktop audio playback. The voice triage tooling (`export_voices.py`, `export_voices.bat`) also lives in the bridge. This change consolidates voice data ownership under `talker_service`, cleans up dead bridge TTS code, and adds missing GAMMA voice themes.

## What Changes

- **Move safetensors repository**: Create `talker_service/voices/` as a flat directory containing only `.safetensors` files (no subdirectories, no source audio)
- **New export script**: Create `tools/voice_triage/phase3_export.py` that reads triaged source audio from `voice_staging/raw/<theme>/` and bakes `.safetensors` to `talker_service/voices/<theme>.safetensors`
- **Add missing GAMMA voice themes**: Run phase1 triage against the Dux Characters Kit mod for 8 missing themes (`csky_2`, `dolg_2`, `freedom_2`, `isg_1`, `killer_2`, `military_2`, `monolith_1`, `monolith_2`)
- **Update service config**: Change `voices_dir` default from `../talker_bridge/voices` to `./voices` (relative to talker_service)
- **Remove `no_speach` and `story`**: Drop these non-speaking voice profiles
- **Remove bridge TTS code**: Strip `TTSQueue`, `load_voice_cache()`, `play_tts()`, `_run_tts_task()`, `tts.speak` handling, `--tts` CLI flag, and `tts.started`/`tts.done` publish calls from `talker_bridge/python/main.py`
- **Remove old bridge voice tooling**: Delete `talker_bridge/python/export_voices.py`, `talker_bridge/python/denoise_worker.py` (if present), and root `export_voices.bat`
- **Remove `LOCAL_TOPICS` entry for `tts.speak`**: Bridge no longer handles TTS locally
- **Clean up Lua `tts.speak` fallback path**: Remove the `tts.speak` publish in `talker_ws_command_handlers.script`'s `handle_dialogue_display`
- **Remove dead Lua voice repo**: Delete `bin/lua/domain/repo/voices.lua` and its test (superseded per `voice-profile-store` spec)
- **Remove `tts_enabled` config getter from Lua**: The Lua side no longer needs to know about TTS — the service handles it entirely

## Capabilities

### New Capabilities
- `voice-export-pipeline`: Defines the phase3 export script that bakes triaged source audio into flat `.safetensors` files for the service, and the phase1 modification to support additional source directories for GAMMA-only voice themes

### Modified Capabilities
- `service-tts-generation`: Voices directory default changes from `../talker_bridge/voices` to `./voices` relative to service root. Flat `.safetensors` layout replaces nested subdirectory structure.

## Impact

- **talker_service/**: New `voices/` directory with ~35 `.safetensors` files (~600MB). Config default change in `config.py`. Engine voice loading glob may simplify (flat only).
- **talker_bridge/python/main.py**: Significant code removal (~100 lines): `TTSQueue` class, TTS helpers, `tts.speak` handler, `--tts` flag parsing, voice cache loading
- **talker_bridge/voices/**: Entire directory becomes obsolete (can be deleted or `.gitignore`d)
- **gamedata/scripts/talker_ws_command_handlers.script**: Remove `tts.speak` fallback in `handle_dialogue_display`
- **bin/lua/domain/repo/voices.lua**: Deleted (dead code per existing spec)
- **bin/lua/interface/config.lua**: Remove `tts_enabled()` getter if present
- **tools/voice_triage/**: New `phase3_export.py` script; `phase1_triage.py` gains optional `--source-dir` and `--only` arguments
- **Root**: `export_voices.bat` deleted
