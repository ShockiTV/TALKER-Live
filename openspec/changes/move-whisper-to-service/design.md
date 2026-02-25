## Context

Currently, the `mic_python` service is responsible for both capturing audio from the user's microphone and transcribing it using Whisper (either locally via PyTorch or via an API). The transcribed text is then sent to the Lua game client, which forwards it to the main `talker_service` for dialogue generation.

Additionally, Lua maintains two separate WebSocket connections: one to `mic_python` (port 5558) for microphone control, and one to `talker_service` (port 5557) for AI dialogue. This dual-connection architecture adds complexity and means Lua needs to know the remote `talker_service` address.

By promoting `mic_python` into `talker_bridge` — a required local WS proxy with integrated audio capture — we achieve a single-connection architecture where Lua only talks to the bridge, and the bridge handles all upstream communication (including audio streaming) with `talker_service`.

## Goals / Non-Goals

**Goals:**
- Move all Speech-to-Text (STT) transcription logic (Whisper local and API) from `mic_python` to `talker_service`.
- Promote `mic_python` into `talker_bridge`: a required local service that proxies all Lua ↔ `talker_service` WS traffic.
- `talker_bridge` captures audio, runs local VAD for silence detection, and streams audio chunks directly to `talker_service` — audio never passes through Lua.
- Lua connects only to `talker_bridge` (localhost) via a single WS connection.
- Ensure `talker_bridge` can be built as a lightweight, standalone `.exe` without heavy dependencies like PyTorch.
- Maintain the existing user experience (push-to-talk hotkey, HUD status updates).

**Non-Goals:**
- Changing the audio capture library (`sounddevice`) in `talker_bridge`.
- Implementing new STT providers (sticking to the existing local Whisper and API options).
- Modifying the Lua game client's hotkey handling logic.

## Decisions

### D1: `talker_bridge` as WS proxy hub

**Decision**: `mic_python` is renamed to `talker_bridge` and becomes a required local service. It acts as a WebSocket proxy: Lua connects to `talker_bridge` on port 5558, and `talker_bridge` maintains an upstream WS connection to `talker_service` (port 5557, local or remote). All Lua ↔ `talker_service` messages are transparently proxied through the bridge.

**Alternatives considered**:
- *Lua connects directly to both mic and service*: The current setup — two WS connections, Lua needs to know remote service URL. More complex.
- *Lua relays audio to service*: Audio payloads would pass through Lua's game thread, risking frame stutters during streaming.
- *mic_python connects directly to talker_service for audio, Lua connects to service separately*: Still two connections from Lua's perspective or requires mic_python to have its own WS client to the service.

**Rationale**: Single-connection architecture for Lua is simplest. `talker_bridge` is always local, so Lua never needs a remote URL. The bridge handles all upstream routing, including audio which bypasses Lua entirely. `talker_bridge` becoming required is acceptable — it replaces both the old mic client AND the direct Lua→service connection.

### D2: Audio streaming with local VAD

**Decision**: `talker_bridge` streams audio chunks to `talker_service` as they are captured, using base64-encoded JSON envelopes (`mic.audio.chunk`). Local Voice Activity Detection (VAD) in `talker_bridge` detects silence/end-of-speech and sends a `mic.audio.end` signal. This allows `talker_service` to begin processing audio as soon as speech starts.

**Alternatives considered**:
- *Send one blob after recording completes*: Simpler but adds latency — Whisper can't start processing until the full recording is available.
- *Raw binary WebSocket frames for audio*: More efficient but breaks the JSON envelope convention.

**Rationale**: Streaming enables Whisper to start processing earlier. Local VAD (using `webrtcvad` or simple energy threshold) ensures instant silence detection without network round-trip. `webrtcvad` is ~200KB — negligible impact on `.exe` size.

### D3: STT integration in `talker_service`

**Decision**: Move the existing `whisper_local.py` and `whisper_api.py` modules from `mic_python` into a new `stt` package within `talker_service`. The `talker_service` will buffer incoming `mic.audio.chunk` messages and run transcription when `mic.audio.end` is received.

**Alternatives considered**:
- *Use a separate microservice for STT*: Over-engineered for the current scope. `talker_service` already handles heavy LLM processing.

**Rationale**: Reusing the existing Whisper integration code minimizes risk and development time.

### D4: `talker_bridge` standalone executable

**Decision**: Strip `talker_bridge` of all STT dependencies (PyTorch, OpenAI Whisper) and update its build script to generate a lightweight PyInstaller `.exe`.

**Alternatives considered**:
- *Rewrite the bridge in Go or Rust*: Smaller executable but requires rewriting audio capture, WS proxy, and VAD from scratch.

**Rationale**: Python with `sounddevice`, `websockets`, and `webrtcvad` can be compiled into a reasonably sized `.exe` (~20-30MB) using PyInstaller, which is acceptable and requires much less effort than a full rewrite.

### D5: WS proxy transparency

**Decision**: `talker_bridge` proxies messages transparently — it does not inspect, transform, or route most messages. It simply forwards Lua→service and service→Lua envelopes as-is. The only topics the bridge handles itself are `mic.start`, `mic.cancel`, `mic.status`, and the audio streaming topics (`mic.audio.chunk`, `mic.audio.end`).

**Alternatives considered**:
- *Bridge inspects and routes all topics*: Adds coupling — bridge needs to know about every topic.

**Rationale**: Transparent proxying means adding new Lua↔service topics requires zero bridge changes. Only mic-related topics are handled locally.

## Risks / Trade-offs

**[Risk] `talker_bridge` is now required** → Users can no longer connect Lua directly to `talker_service` without the bridge.
*Mitigation*: The bridge is lightweight and easy to run. It replaces two separate concerns (mic client + WS connection) with one. Ship as a pre-built `.exe` for zero-setup.

**[Risk] Network latency for audio streaming** → Streaming audio to a remote server adds latency vs local transcription.
*Mitigation*: Streaming chunks as they arrive lets Whisper start processing early, partially offsetting the network cost. OGG/Opus compression keeps payloads small.

**[Risk] `talker_service` dependency bloat** → Adding PyTorch and Whisper to `talker_service` makes it heavier.
*Mitigation*: Make local Whisper an optional dependency (e.g., `pip install .[stt]`) so users can opt for the API version.

**[Risk] Bridge as single point of failure** → If `talker_bridge` crashes, all communication stops.
*Mitigation*: The bridge is minimal code (proxy + audio capture). Robust error handling with auto-reconnect on the upstream connection. Lua's existing reconnect logic handles bridge restarts.