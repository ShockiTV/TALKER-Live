## Context

TTS voice data (`.safetensors` files) currently lives in `talker_bridge/voices/` in nested per-theme subdirectories that also contain raw source audio (`.ogg` files). The `talker_service` is the sole consumer of these files — it loads them at startup for in-engine 3D TTS generation — yet references them cross-package via `voices_dir = ../talker_bridge/voices`.

The bridge retains ~100 lines of dead 2D TTS code (`TTSQueue`, `load_voice_cache`, `play_tts`, `--tts` flag) from the pre-service era when it played audio through desktop speakers. The Lua side still has a `tts.speak` fallback path in `handle_dialogue_display` and a dead `voices.lua` repo module. Voice export tooling (`export_voices.py`, `export_voices.bat`) also lives in the bridge rather than the shared `tools/` directory.

Meanwhile, 8 GAMMA-only voice themes from the Dux Characters Kit are missing from the triage pipeline because `phase1_triage.py` only reads from the base Anomaly unpacked directory.

## Goals

- Consolidate voice data ownership: `talker_service/voices/` becomes the single flat directory of `.safetensors` files
- Create `phase3_export.py` in `tools/voice_triage/` to bake triaged source audio into safetensors
- Add `--source-dir` and `--only` arguments to `phase1_triage.py` so it can target additional voice sources (Dux mod) for the 8 missing themes
- Remove all dead bridge TTS code, old export tooling, Lua fallback paths, and dead voice repo
- Update service config default to point to local `./voices` instead of cross-package path

## Non-Goals

- Changing the TTS engine (pocket_tts) or audio quality pipeline
- Modifying voice selection logic or voice ID resolution
- Changing the in-engine 3D audio playback system (Lua `handle_tts_audio`)
- Re-triaging already-triaged voice themes — the 28 existing themes in `voice_staging/raw/` are kept as-is

## Decisions

### Flat safetensors directory
Voice files live as `talker_service/voices/<theme>.safetensors` with no subdirectories. The engine's glob pattern simplifies from `**/*.safetensors` to `*.safetensors`. This makes the directory easy to enumerate and eliminates confusion between source audio and baked voice caches.

### phase3_export.py reads from voice_staging/raw/
The new export script reads one source `.ogg` file per theme from `voice_staging/raw/<theme>/` and writes to `talker_service/voices/<theme>.safetensors`. This keeps the three-phase triage pipeline (phase1: select candidates → phase2: enhance audio → phase3: bake safetensors) self-contained in `tools/voice_triage/`.

### phase1_triage.py gains --source-dir and --only
Rather than duplicating phase1 for Dux themes, the existing script gets optional CLI arguments: `--source-dir` overrides the default Anomaly unpacked path, and `--only` accepts a comma-separated list of theme names to triage (skipping all others). This lets us run: `python phase1_triage.py --source-dir "F:\GAMMA\mods\305- Dux Characters Kit...\gamedata\sounds\characters_voice\human" --only csky_2,dolg_2,freedom_2,isg_1,killer_2,military_2,monolith_1,monolith_2`

### Delete no_speach and story profiles
These voice profiles have no spoken audio content and serve no purpose for TTS. They are removed from `voice_staging/raw/` and not baked.

### Complete bridge TTS cleanup
All bridge TTS code is removed in one pass: `TTSQueue` class, `load_voice_cache()`, `play_tts()`, `_run_tts_task()`, the `tts.speak` handler in `handle_local_message`, the `--tts` CLI flag, `tts.started`/`tts.done` publish calls, and `LOCAL_TOPICS["tts.speak"]`. The bridge's `pocket_tts` and `sounddevice` imports become unnecessary for TTS (sounddevice may still be needed for mic).

### Remove Lua tts.speak fallback and dead repos
The `handle_dialogue_display` function in `talker_ws_command_handlers.script` loses its `tts.speak` bridge fallback. The dead `bin/lua/domain/repo/voices.lua` and its test are deleted. The `tts_enabled()` config getter is removed from `bin/lua/interface/config.lua` since Lua no longer needs to know about TTS state.

### Old export tooling deleted
`talker_bridge/python/export_voices.py` and root `export_voices.bat` are deleted, replaced by `tools/voice_triage/phase3_export.py`.

## Risks & Trade-offs

### Large binary move (~600MB)
Moving ~35 safetensors files is a filesystem operation, not a code change. The actual move is manual (copy files, verify, delete originals). The change only ensures the config and code point to the right place.

### Bridge --tts users lose functionality
Anyone using `launch_talker_bridge.bat --tts` for 2D desktop TTS playback loses that pathway. This is acceptable because in-engine 3D TTS via the service is strictly superior and the 2D path was never documented as a supported feature.

### pocket_tts import in bridge
After cleanup, the bridge may still import pocket_tts for other reasons (or not at all). Need to verify no remaining bridge code references pocket_tts after TTS removal.
