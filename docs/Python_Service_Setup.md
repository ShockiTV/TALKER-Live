# TALKER Expanded - Python Service Setup

## Overview

**Starting from Phase 2, the Python service is REQUIRED for TALKER Expanded to generate AI dialogue.** This is a breaking change from previous versions.

The Python service handles:
- All LLM calls for dialogue generation
- Speaker selection (choosing which NPC responds)
- Memory compression and long-term memory updates
- Prompt building and context management

Benefits of this architecture:
- Non-blocking game performance (AI processing happens in a separate process)
- Faster response times via async Python HTTP clients
- Future integration with local LLMs
- Advanced memory management and prompt optimization
- Better error handling and retry logic

## Requirements

- Python 3.10 or higher
- 4GB RAM minimum (8GB recommended for local models)
- Windows 10/11
- ~100MB disk space for dependencies

## Installation

### 1. Install Python

Download and install Python from [python.org](https://python.org). Make sure to check "Add Python to PATH" during installation.

### 2. Install the Service

Run the launch script once to set up the virtual environment:

```batch
launch_talker_service.bat
```

This will:
1. Create a Python virtual environment in `talker_service/.venv`
2. Install all required dependencies
3. Start the service

### 3. Start the Game

1. Launch STALKER Anomaly
2. Load a save - dialogue will be generated via the Python service

**Note:** The Python service is always enabled. No MCM toggle is needed.

## Usage

### Starting the Service

1. Run `launch_talker_service.bat` **before** starting the game
2. Start STALKER Anomaly
3. Load a save - dialogue will be generated via the Python service

**IMPORTANT:** The game will NOT generate any AI dialogue if the Python service is not running.

### Checking Health

The service exposes a health endpoint:
- Open browser to `http://localhost:8080/health`
- You should see: `{"status": "ok", "zmq_connected": true, ...}`

### Debug Endpoints

- `http://localhost:8080/debug/config` - View current mirrored MCM config

### Logs

Service logs are written to `talker_service/logs/` directory.

## Configuration

### Environment Variables

Create a `.env` file in `talker_service/` (copy from `.env.example`):

```env
# ZMQ Settings
LUA_PUB_ENDPOINT=tcp://127.0.0.1:5555
SERVICE_PUB_ENDPOINT=tcp://*:5556

# FastAPI Settings
HTTP_HOST=127.0.0.1
HTTP_PORT=8080

# LLM Settings
DEFAULT_LLM_PROVIDER=openai
LLM_TIMEOUT=60.0
STATE_QUERY_TIMEOUT=30.0

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/talker_service.log
```

### MCM Settings

| Setting | Description | Default |
|---------|-------------|---------|
| ZMQ Port | Port for ZeroMQ communication (Lua → Python) | 5555 |
| ZMQ Command Port | Port for command channel (Python → Lua) | 5556 |
| Heartbeat Interval | Seconds between heartbeat messages | 5 |

## Troubleshooting

### Service Won't Start

1. Check Python is installed: `python --version`
2. Check port is not in use: `netstat -an | findstr :5555`
3. Check logs in `talker_service/logs/`

### Game Doesn't Connect

1. Ensure service is running **before** loading a save
2. Verify ports match in MCM and `.env`
3. Check `logs/talker_debug.log` for ZMQ errors
4. A HUD notification will appear if the service is disconnected

### No Dialogue Generated

1. Verify Python service is running and connected (check /health endpoint)
2. Check service logs for LLM errors
3. Verify your API keys are correctly configured

### Missing libzmq.dll (Game Side)

The game (Lua) requires `libzmq.dll` in `bin/pollnet/`. The Python service does NOT need this file (pyzmq bundles its own library).

**Option 1: Download Pre-built**
1. Go to [ZeroMQ Windows releases](https://github.com/zeromq/libzmq/releases)
2. Download the latest `zeromq-*-win64.zip`
3. Extract `bin/libzmq-*.dll`
4. Rename to `libzmq.dll`
5. Place in `bin/pollnet/`

**Option 2: Use vcpkg**
```batch
vcpkg install zeromq:x64-windows
copy %VCPKG_ROOT%\installed\x64-windows\bin\libzmq*.dll bin\pollnet\libzmq.dll
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STALKER Anomaly (Lua)                    │
├─────────────────────────────────────────────────────────────┤
│  talker_zmq_integration.script                              │
│    └─► publisher.lua ──► bridge.lua (LuaJIT FFI)            │
│                              │                               │
│                         libzmq.dll                          │
└──────────────────────────────┼──────────────────────────────┘
                               │ ZMQ PUB/SUB (tcp:5555)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Python Service                            │
├─────────────────────────────────────────────────────────────┤
│  ZMQRouter (subscriber)                                     │
│    └─► handlers/events.py (game events)                     │
│    └─► handlers/config.py (config sync)                     │
│                                                             │
│  FastAPI (http:8080)                                        │
│    └─► /health (health check)                               │
│    └─► /debug/config (view current config)                  │
└─────────────────────────────────────────────────────────────┘
```

## Service Status Notifications

The game will show HUD notifications if the Python service becomes unavailable:

- **"TALKER: Python service not responding. AI dialogue disabled."** - Shown when the service hasn't responded for 15 seconds
- **"TALKER: Python service reconnected. AI dialogue restored."** - Shown when connection is restored

This helps you know if you forgot to start the service or if it crashed.

---

## TTS (Text-to-Speech) Setup

mic_python supports NPC voice synthesis via [Pocket TTS](https://github.com/kyutai-labs/pocket-tts). When enabled, dialogue is queued in Lua, sent to mic_python which streams audio playback, and the HUD subtitle appears in sync with the voice.

### How voice IDs are resolved

Lua calls `npc:sound_prefix()` on each NPC game object, which returns the NPC's engine voice theme path (e.g. `characters_voice\human\stalker_1\`). The last path component (`stalker_1`) is used as the `voice_id` and must match a folder (or flat file stem) under `mic_python/voices/`. If the NPC object is not loaded, a fallback pool from `voice_data.lua` is used.

### Requirements

- `mic_python/.venv` with `pocket-tts` installed (added automatically by `export_voices.bat`)
- A GPU or patient CPU (first chunk from CPU is ~1-3 seconds)
- Anomaly voice files copied into `mic_python/voices/` (see Step 1)

### Step 1 - Copy Anomaly voice theme folders

Copy the entire `gamedata/sounds/characters_voice/human/` directory from your Anomaly installation into `mic_python/voices/`, preserving the subfolder structure:

```
mic_python/voices/
  stalker_1/talk/jokes/   <- source audio picked from here
  stalker_2/talk/jokes/
  bandit_1/talk/jokes/
  dolg_1/talk/jokes/
  ... (all ~28 theme folders)
```

The script automatically selects the longest file from `talk/jokes/` (best voice clone quality), falling back to `states/idle/` for themes that lack jokes (e.g. `monolith_3`, `zombied_1`, `woman`).

### Step 2 - (Optional) Manual voice override

If the auto-selected file gives poor quality (e.g. `stalker_2` or `stalker_4` have drunk/slurred joke lines), place a better `.ogg` directly in the theme root:

```
mic_python/voices/stalker_2/stalker_2.ogg   <- manually placed, never overwritten
```

The script detects and uses this file automatically, skipping subfolder selection.

### Step 3 - Bake voice profiles (run once)

```bat
export_voices.bat
```

For best quality, use DeepFilterNet denoising (requires ~500 MB one-time download of PyTorch):

```bat
export_voices.bat --denoise
```

This will:
1. Install `pocket-tts` into `mic_python/python/.venv`
2. Install `deepfilternet + torch + torchaudio` into a separate `mic_python/python/.venv_df` (avoids numpy conflicts)
3. For each theme: copy the source `.ogg`, optionally denoise it to `<stem>__clean.wav`, export `<stem>.safetensors`

Re-run with `--force` to re-export (e.g. after replacing a manual source file). `--force` never overwrites a manually placed source file.

Skipped folders: `music/`, `story/`, `no_speach/` (no usable voice audio).

### Step 4 - Launch mic_python with TTS enabled

In `launch_mic.bat` -> **Python Launch** menu, choose an option with **TTS**, or invoke directly:

```bat
.venv\Scripts\python.exe main.py whisper_local --tts
```

### Step 5 - Enable TTS in MCM

In the Mod Configuration Menu, enable the **TTS** toggle (`enable_tts = true`). This tells Lua to queue dialogue through mic_python instead of showing it immediately.

### ZMQ topics added by TTS

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `tts.speak` | Lua -> mic_python | Request voice synthesis + playback |
| `tts.started` | mic_python -> Lua | Playback has begun; show HUD subtitle |
| `tts.done` | mic_python -> Lua | Playback complete; dequeue next item |

See [zmq-api.yaml](zmq-api.yaml) for full payload schemas.
