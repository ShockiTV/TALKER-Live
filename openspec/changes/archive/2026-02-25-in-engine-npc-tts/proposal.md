## Why

NPC dialogue audio currently plays through desktop speakers via mic_python (pocket_tts → sounddevice). This means audio has no spatial positioning — it sounds identical regardless of where the NPC is standing — and requires mic_python to run locally on the same machine as the game. Moving TTS playback into the game engine enables 3D spatialized NPC voices (volume/panning based on distance and direction) and decouples the TTS pipeline from the player's machine, supporting server-hosted Python services.

## What Changes

- **New: pre-deployed silent OGG slot files** shipped in `gamedata/sounds/talker_tts/`. The X-Ray engine indexes sound files at startup only and caches content on first play, so slots must exist before the game launches and be written to before their first playback.
- **New: Lua slot manager** that allocates slots round-robin, writes incoming OGG bytes to the slot file, plays via `sound_object:play()` attached to the NPC game object (3D spatial audio that follows the NPC as they move), and recycles slots after playback completes.
- **New: Python OGG generation** in `talker_service` — pocket_tts generates audio, encodes to OGG Vorbis bytes, and sends base64-encoded audio over the existing WS:5557 service channel.
- **New WS topics** on the service channel for TTS audio transport (`tts.audio` Python→Lua, `tts.playing`/`tts.done` Lua→Python).
- **Modified: TTS queue in command handlers** rewired to receive audio from the service channel instead of delegating to mic_python.
- **Modified: mic_python TTS becomes optional** — the `--tts` flag and `tts.speak` handler remain for backward compatibility (desktop speaker fallback) but are no longer the primary playback path.

## Capabilities

### New Capabilities
- `tts-slot-playback`: Lua-side TTS slot file management and in-engine 3D spatial audio playback via X-Ray sound_object API. Covers slot pool lifecycle (deploy, allocate, write, play, recycle), round-robin allocation, `snd_restart` emergency cache flush, and silent OGG restoration after playback.
- `service-tts-generation`: Python-side TTS audio generation in talker_service. Covers pocket_tts integration, OGG Vorbis encoding, base64 transport, voice cache management, and integration with the dialogue generation flow.

### Modified Capabilities
- `ws-api-contract`: New service channel topics for TTS audio transport — `tts.audio` (Python→Lua with base64 OGG payload), `tts.playing` and `tts.done` (Lua→Python for playback lifecycle signaling).
- `mic-tts-engine`: TTS generation and playback via mic_python becomes an optional fallback rather than the primary path. The `--tts` flag and `tts.speak` handler remain but mic_python is no longer required for NPC voice playback.

## Impact

- **Lua (`gamedata/scripts/`)**: `talker_ws_command_handlers.script` TTS queue logic rewired; new script or module for slot management and sound_object playback.
- **Lua (`bin/lua/`)**: New domain service or infra module for slot allocation, OGG file I/O, and playback state tracking (must go through engine facade).
- **Python (`talker_service/`)**: New TTS module for pocket_tts OGG generation; handlers/events.py gains TTS orchestration after dialogue generation; new WS topics registered in ws_router.
- **Wire protocol (`docs/ws-api.yaml`)**: Three new topics documented.
- **Shipped assets**: ~100 silent OGG files in `gamedata/sounds/talker_tts/` (~1KB each).
- **Dependencies**: pocket_tts library added to talker_service requirements (currently only in mic_python). OGG encoding library (e.g., soundfile or pyogg) may be needed.
- **MO2/GAMMA**: Slot files written at runtime go through USVFS to the mod's overwrite directory — no special handling needed, but silent OGG restoration after playback ensures clean state.
- **Backward compatibility**: mic_python TTS path remains functional for users who prefer desktop speaker output or don't want in-engine audio.
