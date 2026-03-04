## Why

The current mic capture pipeline requires `talker_bridge` — a separate Python process — just to capture audio, perform energy-based VAD, and proxy WebSocket traffic. This adds UX friction (users must launch an extra process), architectural complexity (three processes instead of two), and a maintenance burden (Python sounddevice/numpy/soundfile dependencies). Moving mic capture into a native DLL loaded directly by Lua via LuaJIT FFI eliminates the bridge dependency entirely for mic workflows and simplifies the overall architecture.

## What Changes

- **New native DLL** (`talker_audio.dll`): A C library statically linking PortAudio (capture) and libopus (encoding). Runs an internal capture thread, performs energy-based VAD, Opus-encodes audio, and exposes a poll-based API. Built via GitHub Actions CI, committed as a pre-built binary alongside `pollnet.dll`.
- **Rewritten `microphone.lua`**: Switches from bridge WebSocket messages (`mic.start`/`mic.stop`) to direct FFI calls (`ta_start()`/`ta_stop()`/`ta_poll()`). Polls for Opus chunks on the existing game tick and publishes them over the existing WebSocket connection to `talker_service`.
- **Updated `recorder.lua`**: Gets VAD auto-stop signals from `ta_poll()` return codes instead of `mic.stopped` bridge messages. State machine logic (idle → capturing → transcribing) is preserved.
- **Bridge channel simplification**: `mic.start`/`mic.stop` removed from `LOCAL_TOPICS`. Bridge is no longer needed for mic capture. TTS moves to talker_service.
- **Python service audio handler**: Accepts `format: "opus"` chunks alongside existing `"ogg"` format. Decodes Opus for STT pipeline.
- **Graceful fallback**: If `talker_audio.dll` is not present, `pcall(ffi.load, ...)` fails silently and mic features are disabled — same UX as when the bridge isn't running today.

## Capabilities

### New Capabilities
- `native-audio-capture`: Native DLL (PortAudio + Opus) with poll-based FFI API for mic capture, VAD, encoding, and device selection — loaded by LuaJIT inside the game process.
- `audio-dll-ci-build`: GitHub Actions workflow to build `talker_audio.dll` from C source using MSVC + vcpkg (PortAudio, Opus).

### Modified Capabilities
- `mic-audio-streaming`: Audio chunks change from OGG/Vorbis (bridge) to Opus (native DLL). Streaming now originates from Lua's game tick poll, not from bridge's Python thread. Session ID tracking moves to Lua. `mic.stopped` signal comes from `ta_poll()` return code, not a bridge WS message.
- `mic-toggle-state-machine`: `recorder.lua` no longer depends on `bridge_channel.on("mic.stopped", ...)`. VAD auto-stop is detected via `ta_poll() == -1`. Bridge channel mic handlers are removed; replaced by poll-loop integration.
- `service-whisper-transcription`: STT providers must accept Opus-encoded audio in addition to (or instead of) OGG/Vorbis.

## Impact

- **Lua layer** (`bin/lua/infra/mic/`): `microphone.lua` rewritten; new FFI binding module for `talker_audio.dll`; new `audio_tick` poll loop integrated into existing tick timer.
- **Lua layer** (`bin/lua/interface/`): `recorder.lua` updated to remove bridge dependency, use poll-based signals.
- **Python service** (`talker_service/handlers/audio.py`, `talker_service/stt/`): Accept and decode Opus chunks.
- **Native code** (`native/`): New C source (~400 LOC), CMakeLists.txt, vcpkg.json.
- **CI** (`.github/workflows/`): New build workflow for the DLL.
- **Shipped binaries** (`bin/pollnet/`): New `talker_audio.dll` (~300-400KB).
- **Bridge** (`talker_bridge/`): AudioStreamer and mic-related handling become dead code. Bridge may be deprecated or reduced to a TTS-only role (TTS planned to move to talker_service separately).
- **Dependencies**: No new Python dependencies. PortAudio and libopus are statically linked into the DLL at build time.
