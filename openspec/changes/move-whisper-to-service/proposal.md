## Why

Currently, the `mic_python` service handles both microphone audio capture and Whisper Speech-to-Text (STT) transcription locally. As we move towards a remote/server-hosted architecture for the main `talker_service`, requiring users to run a heavy local Python environment (with PyTorch and Whisper models) just for microphone input is a significant barrier.

Additionally, the current architecture requires Lua to maintain two separate WebSocket connections — one to `mic_python` (port 5558) and one to `talker_service` (port 5557). By promoting `mic_python` into `talker_bridge` — a required local proxy that handles audio capture, VAD-based silence detection, audio streaming, and WS proxying — Lua only needs a single connection to the bridge, and the bridge handles all communication with the remote `talker_service`.

## What Changes

- **Renamed**: `mic_python` becomes `talker_bridge` — a required local service that acts as WS proxy + audio capture.
- **New**: `talker_bridge` proxies all Lua ↔ `talker_service` WS traffic transparently, so Lua only connects to the bridge.
- **New**: `talker_bridge` captures audio, runs local Voice Activity Detection (VAD) for silence detection, and streams audio chunks directly to `talker_service`.
- **New**: `talker_service` gains the ability to receive streamed audio and transcribe it using Whisper (local model or API).
- **Removed**: Lua's direct WS connection to `talker_service` (service-channel) is replaced by the bridge proxy.
- **Removed**: Whisper/STT dependencies removed from `talker_bridge` (moved to `talker_service`).

## Capabilities

### New Capabilities
- `service-whisper-transcription`: The main `talker_service` handles STT transcription of incoming audio streams.
- `mic-audio-streaming`: `talker_bridge` captures audio with local VAD and streams it to `talker_service`.

### Modified Capabilities
- `ws-api-contract`: Update the WebSocket protocol to support audio streaming and the bridge proxy architecture.

## Impact

- **Python (`talker_service/`)**: Needs new dependencies (Whisper, PyTorch, or API clients) and new WebSocket handlers for audio streams.
- **Python (`mic_python/` → `talker_bridge/`)**: Gains WS proxy responsibility. Stripped of Whisper/STT dependencies. Adds lightweight VAD (`webrtcvad` or energy-based). Becomes a required component (not optional). Buildable as standalone `.exe`.
- **Lua (`bin/lua/infra/`)**: Simplified — single WS connection to `talker_bridge` instead of two channels (mic-channel + service-channel). The bridge transparently proxies all traffic.
- **Wire protocol (`docs/ws-api.yaml`)**: New `mic.audio.chunk` and `mic.audio.end` topics for audio streaming between bridge and service.
- **Deployment**: `talker_bridge` is always required (replaces both the old mic client and the direct Lua→service connection). Users no longer need a full Python environment locally for STT — only for `talker_service` if self-hosted.