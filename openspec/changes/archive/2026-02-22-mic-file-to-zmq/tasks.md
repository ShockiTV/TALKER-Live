```markdown
## 1. mic_python ZMQ Transport (Python side)

- [x] 1.1 Rewrite `mic_python/python/main.py` — replace watchdog file monitor with synchronous ZMQ SUB/PUB loop (SUB on :5555 filtered to `mic.`, PUB bound on :5557), dispatch `mic.start`→record session, `mic.stop`→cancel, publish `mic.status` and `mic.result`
- [x] 1.2 Delete `mic_python/python/files.py` (temp file helpers no longer needed)
- [x] 1.3 Update `mic_python/python/requirements.txt` — remove `watchdog`, add `pyzmq`
- [x] 1.4 Update `mic_python/python/build.bat` — add `--hidden-import=zmq` to PyInstaller command

## 2. Lua ZMQ Bridge Extension

- [x] 2.1 Extend `bin/lua/infra/zmq/bridge.lua` — add mic SUB socket connecting to tcp://127.0.0.1:5557, subscribe to `mic.` prefix, poll both SUB sockets in `poll_commands()`
- [x] 2.2 Update bridge shutdown to close the mic SUB socket alongside existing PUB and primary SUB

## 3. Lua Microphone Module Rewrite

- [x] 3.1 Rewrite `bin/lua/infra/mic/microphone.lua` — replace `file_io.override_temp()` calls with `bridge.publish("mic.start", ...)` and `bridge.publish("mic.stop", {})`, add ZMQ handler registration for `mic.status` and `mic.result` to update internal state
- [x] 3.2 Remove `file_io` dependency from microphone.lua; remove all temp file reads/writes

## 4. Lua Recorder Module Rewrite

- [x] 4.1 Rewrite `bin/lua/interface/recorder.lua` — replace `game_adapter.repeat_until_true` polling loop with ZMQ handler-based push: register handlers for `mic.status` (display to player) and `mic.result` (invoke callback with text), clean up handlers after result received

## 5. Wire Protocol Documentation

- [x] 5.1 Update `docs/zmq-api.yaml` — add `mic.start`, `mic.stop` (direction: lua→mic_python) and `mic.status`, `mic.result` (direction: mic_python→lua) message definitions with payload schemas

## 6. Launch Script Update

- [x] 6.1 Update `launch_mic.bat` — remove any temp-file setup/cleanup, ensure mic_python launches with correct Python/venv and passes provider argument

## 7. Verification

- [x] 7.1 Manual integration test: launch mic_python + game, trigger mic.start from Lua, verify LISTENING→TRANSCRIBING→result flow over ZMQ
- [x] 7.2 Verify mic_python handles absent Lua gracefully (starts without game running, no crash)
- [x] 7.3 Verify bridge.lua handles absent mic_python gracefully (poll_commands returns normally when mic not running)

```