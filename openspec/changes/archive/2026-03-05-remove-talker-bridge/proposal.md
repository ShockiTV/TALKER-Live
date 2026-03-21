## Why

The `talker_bridge` service is now a vestigial component. It was originally needed for three purposes: local TTS playback, local microphone capture, and proxying WebSocket traffic between Lua and `talker_service`. All three have been superseded:

- **TTS**: Moved to `talker_service` (generates OGG, publishes `tts.audio` directly). The bridge's `tts.speak` handler was already removed per `service-tts-generation` spec.
- **Mic capture**: Replaced by `talker_audio.dll` (native DLL loaded via LuaJIT FFI). The bridge's `mic.start`/`mic.stop` local handlers have zero callers.
- **WS proxy**: Pure passthrough — every message is forwarded unchanged. Adds latency, an extra process to launch, and a failure point with no functional benefit.

Removing the bridge simplifies user setup (one fewer service to launch), reduces debugging complexity (one fewer WS hop), and eliminates dead code.

## What Changes

- **BREAKING**: Remove `talker_bridge/` directory and `launch_talker_bridge.bat`
- **BREAKING**: Lua connects directly to `talker_service` (port 5557) instead of bridge (port 5558)
- Rename `infra/bridge/channel.lua` → `infra/ws/service_channel.lua` (or equivalent) since the channel implementation is reusable; only the target URL changes
- Update MCM default port from 5558 → 5557; rename `mic_ws_port` to `service_ws_port`
- Remove bridge-specific test files (Lua and Python)
- Update `talker_ws_integration.script` to build service URL directly
- Update documentation (AGENTS.md, README.md, ws-api.yaml, setup docs)

## Capabilities

### New Capabilities
- `direct-lua-service-connection`: Lua game client connects directly to `talker_service` WebSocket endpoint, removing the bridge intermediary

### Modified Capabilities
- `ws-api-contract`: Remove bridge from communication flow; Lua connects directly to service on port 5557. Direction labels change from `lua→bridge→service` to `lua→service`.
- `mic-ws-channel`: Channel module renamed from `infra/bridge/channel` to reflect direct service connection. URL construction changes to target service directly.
- `service-tts-generation`: Remove references to bridge TTS fallback (already dead, just cleanup stale references in spec).
- `talker-mcm`: Rename `mic_ws_port` setting to `service_ws_port`, change default from 5558 to 5557.
- `bridge-remote-config`: This entire capability is obsolete (bridge config peeking for upstream reconnection). Remove or archive.

## Impact

- **Lua runtime**: `infra/bridge/channel.lua` renamed/moved; all `require("infra.bridge.channel")` paths updated. `talker_ws_integration.script` URL construction simplified. `talker_mcm.script` field renamed.
- **Python service**: No code changes needed — it already serves `/ws` on port 5557. Only test assertion strings change (`lua→bridge→service` → `lua→service`).
- **User setup**: Users no longer need to run `launch_talker_bridge.bat`. Only `launch_talker_service.bat` required.
- **VPS/remote deployment**: Works unchanged — Lua connects to `service_url` from MCM directly (no local bridge needed).
- **Tests**: Bridge-specific tests deleted. Bridge channel tests updated to test the renamed module. E2E direction assertions updated.
- **Documentation**: AGENTS.md architecture diagram, README launch instructions, ws-api.yaml flow descriptions, Python_Service_Setup.md all updated.
