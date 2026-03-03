## 1. Native DLL — C Source & Build System

- [x] 1.1 Create `native/` directory with `CMakeLists.txt`, `vcpkg.json` (portaudio, opus dependencies)
- [x] 1.2 Implement `talker_audio.c` — DLL lifecycle (`ta_open`, `ta_close`), PortAudio init/teardown
- [x] 1.3 Implement SPSC lock-free ring buffer (~200 slots, atomic read/write indices)
- [x] 1.4 Implement capture start/stop (`ta_start`, `ta_stop`, `ta_is_capturing`) — PortAudio stream open/close, ring buffer flush on restart
- [x] 1.5 Implement Opus encoder init and PortAudio callback — encode 20ms frames, push to ring buffer
- [x] 1.6 Implement `ta_poll(buf, buf_len)` — drain one frame, return >0/0/-1/-2 status codes; drain all frames before emitting stop signal
- [x] 1.7 Implement energy-based VAD — running mean amplitude, configurable threshold/silence duration, auto-stop on sustained silence
- [x] 1.8 Implement `ta_set_vad(energy_threshold, silence_ms)` with defaults (1000, 2000)
- [x] 1.9 Implement device enumeration (`ta_get_device_count`, `ta_get_device_name`, `ta_get_default_device`) and selection (`ta_set_device`)
- [x] 1.10 Implement Opus config setters (`ta_set_opus_bitrate`, `ta_set_opus_frame_ms`, `ta_set_opus_complexity`) with defaults (24000, 20, 5)
- [x] 1.11 Add `__declspec(dllexport)` / `extern "C"` for all 16 `ta_*` symbols; verify with `dumpbin /exports`
- [x] 1.12 Configure CMake for static CRT (`/MT`), static PortAudio + Opus linkage, x64 shared library output

## 2. GitHub Actions CI Workflow

- [x] 2.1 Create `.github/workflows/build-talker-audio.yml` — trigger on `native/**` and workflow file changes
- [x] 2.2 Configure workflow: `windows-latest`, vcpkg cache, `cmake --build` with MSVC, upload `talker_audio.dll` artifact
- [ ] 2.3 Verify CI produces a working x64 DLL; commit initial binary to `bin/pollnet/talker_audio.dll`

## 3. Lua FFI Binding Module

- [x] 3.1 Create `bin/lua/infra/mic/talker_audio_ffi.lua` — `ffi.cdef` declarations for all 16 `ta_*` functions, `pcall(ffi.load, ...)` with graceful fallback
- [x] 3.2 Export a Lua-friendly wrapper table: `open()`, `close()`, `start()`, `stop()`, `is_capturing()`, `poll()`, `set_vad()`, device functions, opus functions, `is_available()` flag
- [x] 3.3 Write tests for FFI module — mock `ffi.load` failure path (DLL absent → `is_available() == false`)

## 4. Rewrite `microphone.lua` — FFI Instead of Bridge Messages

- [x] 4.1 Replace `bridge_channel.publish("mic.start", ...)` with `ta_start()` FFI call in `start_capture()`
- [x] 4.2 Replace `bridge_channel.publish("mic.stop", {})` with `ta_stop()` FFI call in `stop_capture()`
- [x] 4.3 Keep `is_recording()` / `on_stopped()` API surface; `on_stopped()` just clears the flag (no FFI call — DLL already stopped)
- [x] 4.4 Add `session_id` counter — increment on each `start_capture()` call
- [x] 4.5 Update tests for `microphone.lua` — assert FFI calls instead of bridge publishes

## 5. Audio Tick Polling Loop

- [x] 5.1 Create `bin/lua/infra/mic/audio_tick.lua` — poll loop called from existing tick timer
- [x] 5.2 Implement drain logic: call `ta_poll()` in a loop (up to N per tick), base64-encode each Opus frame, publish `mic.audio.chunk` with `{format: "opus", session_id, seq, data}` to service channel
- [x] 5.3 Handle return code `-1` (VAD auto-stop): trigger recorder's VAD-stopped transition, send `mic.audio.end`
- [x] 5.4 Handle return code `-2` (manual stop): send `mic.audio.end` (no recorder transition — already handled by toggle)
- [x] 5.5 Integrate `audio_tick.tick()` call into existing tick timer (alongside `bridge_channel.tick()` or service channel tick)
- [x] 5.6 Write tests for audio tick — mock FFI poll returning frames then stop codes, assert correct WS publishes and recorder transitions

## 6. Update `recorder.lua` — Remove Bridge Dependency

- [x] 6.1 Remove `bridge_channel.on("mic.stopped", ...)` handler
- [x] 6.2 Remove `bridge_channel.on("mic.status", ...)` handler (or move to service channel if needed)
- [x] 6.3 Register `mic.result` handler on service channel instead of bridge channel
- [x] 6.4 Add public `on_vad_stopped()` method callable by the audio tick loop (replaces the old `mic.stopped` handler)
- [x] 6.5 Update tests — verify state transitions via `on_vad_stopped()` instead of bridge events, verify `mic.result` via service channel

## 7. Bridge Channel Cleanup

- [x] 7.1 Remove `"mic.start"` and `"mic.stop"` from `LOCAL_TOPICS` in `bridge_channel.lua`
- [x] 7.2 Remove any mic-related handler registrations from bridge channel setup code
- [x] 7.3 Verify bridge channel still functions for non-mic traffic (TTS, WS proxy)

## 8. Python Service — Opus Audio Support

- [x] 8.1 Add Opus decode dependency (`opuslib` or `pyogg`) to `talker_service` requirements
- [x] 8.2 Update `handlers/audio.py` — detect `format: "opus"` in `mic.audio.chunk`, store raw Opus frames in buffer
- [x] 8.3 Implement Opus-to-PCM decode in audio handler finalization: decode each frame to 16kHz mono PCM, concatenate
- [x] 8.4 Pass decoded PCM to existing STT provider pipeline (unchanged from current OGG flow post-decode)
- [x] 8.5 Keep OGG format support for backward compat with legacy bridge connections
- [x] 8.6 Write Python tests — Opus chunk buffering, decode-to-PCM, session management, stale session rejection

## 9. Integration Testing & Documentation

- [x] 9.1 End-to-end test: Lua FFI mock → audio tick → WS publish → service receives Opus → STT result → mic.result back to Lua
- [x] 9.2 Test graceful fallback: DLL absent → mic features disabled, no crash
- [x] 9.3 Update `docs/ws-api.yaml` — add `format: "opus"` to `mic.audio.chunk` schema
- [x] 9.4 Update AGENTS.md and README.md — document native mic capture, remove bridge-required language for mic
