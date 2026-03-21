## Context

The `talker_bridge` was introduced as a local Python process sitting between Lua (port 5558) and `talker_service` (port 5557). It served three purposes:

1. **Local TTS playback** — Superseded by `service-tts-generation` (TTS now runs in `talker_service`, audio sent as `tts.audio` with base64 OGG).
2. **Local mic capture** — Superseded by `talker_audio.dll` (native DLL handles PortAudio capture, Opus encoding, and VAD; Lua streams frames directly to service).
3. **WS proxy** — Pure passthrough; no inspection or transformation of messages beyond `config.sync`/`config.update` peeking for its own reconnection logic.

The bridge's `LOCAL_TOPICS` set (`mic.start`, `mic.stop`) has zero callers — no Lua code publishes these topics anymore. The bridge is now a latency-adding, failure-prone middleman.

`talker_service` already serves a FastAPI WebSocket endpoint at `/ws` on port 5557. Lua connecting directly requires only a URL change.

## Goals / Non-Goals

**Goals:**
- Eliminate the bridge process entirely (zero runtime footprint)
- Lua connects directly to `talker_service` on port 5557 (or remote URL from MCM)
- Preserve the channel module's WS state machine (rename, don't rewrite)
- Clean up all bridge references in code, tests, and documentation
- MCM `service_url` field becomes the direct connection target (same field, different consumer)

**Non-Goals:**
- Rewriting the channel state machine (it works well, just rename)
- Changing the wire protocol (same JSON envelopes, same topics)
- Adding new features (this is purely a removal/simplification)
- Changing how mic audio flows (native DLL → service is already direct)

## Decisions

### 1. Rename `infra/bridge/channel.lua` → keep at `infra/bridge/channel.lua`

**Decision**: Keep the file at its current path. The module is a generic WS channel with state machine, backoff, queue, and request/response correlation. Renaming is cosmetic churn that would touch every `require()` call, every test mock preload, and every script reference. The word "bridge" in the path is just a directory name.

**Alternative considered**: Move to `infra/ws/channel.lua`. Rejected because `infra/ws/` already has `client.lua`, `codec.lua`, and `serializer.lua` — adding `channel.lua` there could confuse the layer (channel is higher-level than the raw WS primitives). A directory rename from `bridge/` to `channel/` would also work but is still churn for no runtime benefit.

### 2. URL construction: use `service_url` directly

**Decision**: `talker_ws_integration.script`'s `get_bridge_url()` function will be renamed to `get_service_url()` and will build the URL from MCM `service_url` directly. For local users, the default remains `ws://127.0.0.1:5557/ws`. For remote users, the MCM `service_url` value (e.g., `wss://talker-live.duckdns.org/ws`) is used as-is with `?token=` appended if `ws_token` is set.

The `mic_ws_port` MCM field is renamed to `service_ws_port` with default 5557, used only for local connections (when `service_url` is empty or localhost). When `service_url` is a full URL (contains `://`), the port field is ignored.

### 3. Delete `talker_bridge/` entirely

**Decision**: Remove the entire `talker_bridge/` directory tree, `launch_talker_bridge.bat`, `test_bridge_config_issue.py`, and all bridge-specific Python tests (`test_bridge_config.py`, `test_bridge_lua_closure.py`). Also remove `tests/integration/test_bridge_config_sync.py`.

**Alternative considered**: Keep as deprecated code. Rejected — dead code rots and confuses contributors.

### 4. Keep `bridge-remote-config` spec but mark as removed

**Decision**: The spec described bridge-side config peeking for upstream reconnection. This behavior is no longer needed — Lua builds the service URL directly from MCM values. The spec will be marked as removed in the delta spec.

### 5. Update E2E test direction assertions

**Decision**: Change direction strings from `"lua→bridge→service"` to `"lua→service"` and `"service→bridge→lua"` to `"service→lua"` in the E2E WS API contract tests. These are documentation assertions, not behavioral tests.

## Risks / Trade-offs

**[Risk: Users with existing MCM configs targeting port 5558]** → The MCM default changes from 5558 to 5557. Users who never changed the default will get the new default automatically. Users who explicitly set port 5558 in MCM will need to update. Mitigation: CHANGELOG entry explaining the change. The field rename from `mic_ws_port` to `service_ws_port` will also reset the value to default for all users.

**[Risk: Remote users relying on bridge for local connection multiplexing]** → No impact. Remote users set `service_url` in MCM, which now goes directly to the service instead of through the bridge. The bridge was already just forwarding these connections.

**[Risk: Breaking change for users who launch bridge separately]** → `launch_talker_bridge.bat` is deleted. Users who have it in their startup scripts will see it missing. Mitigation: Clear CHANGELOG entry, README update.

**[Trade-off: Losing bridge's AudioStreamer mic capture as legacy fallback]** → The bridge's AudioStreamer (sounddevice + OGG + VAD) was the pre-DLL mic capture path. With the native DLL now handling all mic capture, this fallback is dead code. Accepted — the DLL is the only supported capture path.
