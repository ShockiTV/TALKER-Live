## Context

Today, mic capture runs in `talker_bridge` — a separate Python process that captures audio via `sounddevice`, performs energy-based VAD, compresses to OGG/Vorbis, and streams base64-encoded chunks over WebSocket to `talker_service`. Lua merely sends `mic.start`/`mic.stop` commands and receives `mic.stopped`/`mic.result` signals back. The bridge also proxies all other WS traffic (game events, config, dialogue) between Lua and the service.

This design moves mic capture into a native C DLL (`talker_audio.dll`) loaded by LuaJIT FFI, so the game process handles capture, VAD, and Opus encoding internally. Lua polls for encoded chunks on its existing 50ms tick and sends them over the existing pollnet WebSocket — no second process, no proxy layer.

**Current flow:**
```
Lua → mic.start → bridge (Python) → sounddevice capture → OGG encode → mic.audio.chunk → service
Lua ← mic.stopped ← bridge ← VAD silence detection
```

**New flow:**
```
Lua → ta_start() → talker_audio.dll (PortAudio capture thread) → Opus encode → ring buffer
Lua tick: ta_poll() → opus bytes → WS send mic.audio.chunk → service
Lua tick: ta_poll() == -1 → VAD stopped → WS send mic.audio.end → service
```

## Goals / Non-Goals

**Goals:**
- Eliminate `talker_bridge` as a dependency for mic capture workflows
- Ship a native DLL with PortAudio + Opus statically linked, built via GitHub Actions
- Provide a complete poll-based C API (14 functions) covering capture lifecycle, VAD config, device selection, and Opus tuning
- Maintain the existing recorder state machine (`idle → capturing → transcribing`) and user-facing behavior
- Accept Opus-encoded audio in `talker_service` STT pipeline
- Graceful fallback when DLL is absent (mic features disabled, no crash)

**Non-Goals:**
- TTS playback from Lua (separate concern; TTS will migrate to `talker_service` independently)
- Removing `talker_bridge` entirely (it still serves as WS proxy for remote deployments and may handle TTS until migrated)
- WebRTC VAD or ML-based VAD (energy-based is sufficient and keeps the DLL dependency-free beyond PortAudio/Opus)
- Cross-platform support (STALKER Anomaly is Windows-only; DLL targets x64 Windows)
- Local whisper/STT in the DLL (STT stays in Python service)

## Decisions

### Decision 1: Architecture 1 — "Smart Buffer" (DLL captures, Lua polls & sends)

**Choice:** The DLL captures audio and fills a ring buffer. Lua polls on each game tick and sends chunks over the existing pollnet WebSocket.

**Alternatives considered:**
- *Architecture 2 — Autonomous WS*: DLL opens its own WebSocket connection and sends chunks directly. **Rejected** because: requires embedding a WS+TLS client in the DLL (~1500 LOC), creates two WS connections to correlate, needs reconnect logic, config propagation, and is much harder to test.
- *Shared-memory / file-based IPC*: Lua reads chunks from a temp file or memory-mapped region. **Rejected** because: more complex than a simple FFI poll call, and the polling model fits naturally into the existing tick-based architecture.

**Rationale:** pollnet is not thread-safe (single `pollnet_ctx*`, no locking). The DLL's capture thread cannot call pollnet. But the Lua tick is already running ≤50ms and the cost of one `ta_poll()` + `pollnet_send()` per tick is ~5μs — negligible.

### Decision 2: PortAudio for capture, Opus for encoding

**Choice:** Statically link PortAudio (~150KB) and libopus (~200KB) into the DLL.

**Alternatives considered:**
- *WASAPI-only (no PortAudio)*: Saves ~150KB, zero external deps. **Rejected** because: PortAudio abstracts device enumeration and callback setup cleanly; WASAPI COM boilerplate is error-prone and harder to maintain.
- *Raw PCM (no Opus)*: Fewer deps, simpler. **Deferred** as a fallback: raw PCM works fine for local service (~6.4KB/chunk), but Opus (~300-500 bytes/chunk) is essential for remote service. Since Opus is trivial to include and the DLL is built in CI, there's no reason to omit it.
- *OGG/Vorbis (match current format)*: Would require no service-side changes. **Rejected** because: Opus is superior for voice at low bitrates, and the service-side change to accept Opus is minimal.

### Decision 3: PortAudio callback → lock-free ring buffer → poll drain

**Choice:** PortAudio's audio callback (OS-level thread) writes Opus-encoded frames into a lock-free SPSC (single-producer single-consumer) ring buffer. `ta_poll()` drains the consumer side.

**Rationale:** The callback fires every ~20ms (Opus frame size). Lua polls every ~50ms. A ring buffer of ~4 seconds (~200 Opus frames) ensures no data loss even if the game hitches. SPSC ring buffers need no mutexes — a single atomic write/read index suffices.

### Decision 4: Poll return codes for signaling

**Choice:** `ta_poll()` returns:
- `>0` — Opus bytes written to output buffer
- `0` — Nothing ready (still capturing)
- `-1` — VAD silence detected (auto-stopped)
- `-2` — Manual stop via `ta_stop()`

The DLL drains all remaining buffered chunks before returning the stop signal, ensuring no audio data is lost.

**Rationale:** This eliminates any need for callbacks, shared memory signals, or IPC. The polling model maps naturally to the existing `bridge_channel.tick()` cadence.

### Decision 5: Full API surface from day one (14 functions)

**Choice:** Export all 14 functions including device selection and Opus config, even though defaults suffice for Phase 1.

**Rationale:** Changing a DLL's exported API is more disruptive than changing Lua code (binary compatibility). Unused setters cost ~3 lines of C each. The Lua side can call them later without requiring a new DLL build.

### Decision 6: GitHub Actions CI for DLL builds

**Choice:** Build the DLL via a GitHub Actions workflow using `windows-latest` (MSVC pre-installed) + vcpkg for PortAudio and Opus. Commit the resulting binary to the repo.

**Alternatives considered:**
- *Local builds only*: Requires devs to install VS Build Tools. **Rejected** for contributor friction.
- *MinGW/MSYS2*: Lighter toolchain but potential CRT mixing issues with the MSVC-built game. **Rejected.**
- *Zig as C compiler*: Clean cross-compilation but still needs PortAudio/Opus headers. Viable but unnecessary when CI has MSVC.

### Decision 7: Opus format on the wire, hardcoded on both sides

**Choice:** Lua always sends `format: "opus"` in chunk payloads. Service always expects Opus from Lua (can still accept OGG from legacy bridge connections). No negotiation.

**Rationale:** Both sides are in the same repo and deployed together. Format negotiation adds complexity for zero benefit.

## Risks / Trade-offs

**[Audio device conflicts]** → PortAudio and the game engine both access audio hardware. PortAudio uses a separate capture device (microphone) while the game uses playback devices, so conflicts are unlikely. If issues arise, PortAudio's device enumeration API (`ta_get_device_count()`, `ta_get_device_name()`, `ta_set_device()`) allows explicit device selection.

**[Game hitches during capture]** → If the game stutters (>2s), the ring buffer may fill. Mitigation: 4-second ring buffer (~200 Opus frames at 20ms each). If it overflows, oldest frames are dropped — acceptable for voice capture. VAD silence timer would also trigger during a stall, which is correct behavior.

**[DLL load failure on some systems]** → Missing Visual C++ runtime or AV quarantine. Mitigation: `pcall(ffi.load, ...)` fallback disables mic features gracefully. Ship with static CRT linkage (`/MT`) to avoid runtime dependency.

**[Opus decode support in Python]** → Service needs a new decoder. Mitigation: `opuslib` (ctypes-based) or `pyogg` handle Opus decoding. Alternatively, raw PCM fallback can be added to the DLL API if Opus decode proves problematic.

**[Maintenance burden of native code]** → C code is harder to debug than Lua/Python. Mitigation: The DLL is ~400 LOC with a stable, minimal API. Audio capture APIs don't change. Expected rebuild frequency: <1/year.

## Open Questions

- **Static CRT vs dynamic CRT**: `/MT` (static) avoids runtime dependency but increases DLL size by ~100KB. `/MD` (dynamic) requires Visual C++ Redistributable on the user's machine. Leaning toward `/MT` since STALKER modders may not have the runtime installed.
- **Ring buffer overflow policy**: Drop oldest frames (current plan) vs block the capture callback? Blocking would cause audio glitches. Dropping seems better — lost frames during a game stutter are acceptable.
