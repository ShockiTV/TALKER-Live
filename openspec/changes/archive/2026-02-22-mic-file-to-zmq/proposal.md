## Why

The microphone system (`mic_python`) communicates with the game via temp-file polling (watchdog monitors `%TEMP%\talker_mic_io_commands`), while the rest of the system uses ZeroMQ. This creates fragility (file I/O race conditions, OS quirks) and prevents running the talker_service remotely — a prerequisite for planned multi-tenant deployment. Migrating to ZMQ unifies IPC under one mechanism and decouples mic_python from filesystem locality.

## What Changes

- **mic_python/python/main.py**: Replace watchdog file-monitoring loop with ZMQ SUB/PUB (subscribe to `mic.*` from Lua PUB on :5555, publish results on a new PUB socket :5557)
- **mic_python/python/files.py**: **Remove** — no longer needed (file read/write helpers for temp file IPC)
- **mic_python/python/requirements.txt**: Replace `watchdog` dependency with `pyzmq`
- **mic_python/python/build.bat**: Add `--hidden-import=zmq` for PyInstaller
- **bin/lua/infra/mic/microphone.lua**: Replace `file_io.override_temp` / `file_io.read_temp` calls with `bridge.publish()` for sending commands and ZMQ handler registration for receiving status/results
- **bin/lua/interface/recorder.lua**: Replace `game_adapter.repeat_until_true` file-polling loop with ZMQ-based push notification handling (mic_python pushes status and result via ZMQ)
- **bin/lua/infra/zmq/bridge.lua**: Add a second SUB socket connecting to mic_python PUB on :5557, poll both SUB sockets in `poll_commands()`
- **docs/zmq-api.yaml**: Add `mic.start`, `mic.stop`, `mic.status`, and `mic.result` topic definitions
- **launch_mic.bat**: Update to support both exe and Python-based launch

## Capabilities

### New Capabilities
- `mic-zmq-transport`: ZMQ-based command/result transport between game (Lua) and mic_python, replacing temp-file IPC. Covers the new ZMQ topics (`mic.start`, `mic.stop`, `mic.status`, `mic.result`), the mic_python ZMQ subscriber/publisher, and the second SUB socket in bridge.lua.

### Modified Capabilities
- `lua-zmq-bridge`: Bridge gains a second SUB socket (port 5557 for mic_python PUB) and `poll_commands()` polls both sockets.
- `zmq-api-contract`: New mic-related topics added to the wire protocol schema.

## Impact

- **mic_python**: `main.py` rewritten (~80 lines), `files.py` deleted. `recorder.py` and all transcription providers unchanged.
- **Lua infra**: `microphone.lua` and `recorder.lua` rewritten to use ZMQ instead of file I/O. `bridge.lua` extended with second SUB socket.
- **Dependencies**: `pyzmq` added to mic_python requirements, `watchdog` removed.
- **User-facing**: `launch_mic.bat` updated. Mic exe still distributed for users without Python. No MCM changes.
- **Wire protocol**: Four new ZMQ topics added. Existing topics unchanged.
- **talker_service**: No changes required.
