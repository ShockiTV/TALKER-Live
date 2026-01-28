## Context

TALKER Expanded currently runs all AI logic (LLM calls, prompt building, memory compression) within Lua scripts executed by the STALKER Anomaly game engine. This creates several challenges:
- Lua's callback-based async is difficult to debug
- Testing requires mocking game engine APIs
- Limited library ecosystem compared to Python
- Hot-reload requires game restart

The game persists state (event_store, memory_store, MCM config) in save files, and this must remain in Lua. The Python service will be a **compute-only** layer that queries Lua for state and sends commands back.

Current architecture:
```
Trigger → talker.register_event() → AI_request → LLM → Display
```

Phase 1 target architecture:
```
Trigger → talker.register_event() → (existing flow unchanged)
       ↘ zmq_publisher.send()    → Python (logging only in Phase 1)
```

## Goals / Non-Goals

**Goals:**
- Establish ZeroMQ-based bidirectional communication between Lua and Python
- Create Python service skeleton with FastAPI + pyzmq
- Publish game events from Lua to Python in parallel (fire-and-forget)
- Sync MCM configuration to Python on settings change and game load
- Implement heartbeat mechanism for connection health monitoring
- Zero breaking changes - existing Lua AI flow continues to work

**Non-Goals:**
- Moving AI logic to Python (Phase 2+)
- Python querying Lua stores (Phase 2+)
- Python sending commands back to Lua (Phase 2+)
- Replacing existing Lua AI code (Phase 2+)
- Performance optimization of ZMQ transport

## Decisions

### D1: ZeroMQ Socket Pattern

**Decision:** Use PUB/SUB pattern for Phase 1 (Lua PUB → Python SUB)

**Alternatives Considered:**
- REQ/REP: Synchronous, would block game loop
- PUSH/PULL: No topic filtering, harder to extend
- ROUTER/DEALER: Overkill for Phase 1

**Rationale:** PUB/SUB allows fire-and-forget from Lua (non-blocking), topic-based filtering in Python, and easy extension to bidirectional in Phase 2 (add second PUB/SUB pair in reverse direction).

### D2: ZeroMQ Binding for Lua

**Decision:** Use lzmq (LuaJIT FFI binding) with libzmq.dll

**Alternatives Considered:**
- lua-zmq (C binding): Requires compilation, harder to distribute
- File-based IPC: Simpler but slower, no real-time capability
- HTTP polling: Higher latency, more overhead

**Rationale:** lzmq is pure Lua using FFI, only needs the libzmq.dll binary. STALKER Anomaly uses LuaJIT, so FFI is available. DLL goes in `bin/pollnet/` alongside existing network DLLs.

### D3: Python Framework

**Decision:** FastAPI + pyzmq with asyncio

**Alternatives Considered:**
- Plain asyncio + pyzmq: Less structure, more boilerplate
- Flask + threading: No native async, harder to integrate ZMQ
- FastStream: Newer, less community support

**Rationale:** FastAPI provides optional HTTP endpoints for health checks and debugging UI. Its dependency injection and Pydantic integration work well with pyzmq. ZMQ runs in background task, FastAPI handles HTTP.

### D4: Message Format

**Decision:** JSON with topic prefix

Format: `<topic> <json-payload>`
Example: `game.event {"type":"DEATH","context":{...},"game_time_ms":12345}`

**Alternatives Considered:**
- Protocol Buffers: Better performance, but adds complexity and code generation
- MessagePack: Binary, harder to debug
- Plain JSON without topic: Requires parsing to route

**Rationale:** JSON is human-readable (easier debugging), Lua has json.lua, Python has stdlib json. Topic prefix enables ZMQ's built-in subscription filtering.

### D5: Service Location

**Decision:** `talker_service/` at project root (same level as `mic_python/`)

**Alternatives Considered:**
- `bin/python/talker_service/`: Inside bin folder
- Merge with `mic_python/`: Single Python process

**Rationale:** Consistent with existing `mic_python/` location. Keeps Python services at root level for discoverability. Separate from mic to allow independent operation and future separation of concerns.

### D6: libzmq.dll Location

**Decision:** `bin/pollnet/libzmq.dll`

**Alternatives Considered:**
- `bin/libzmq.dll`: Root of bin
- `talker_service/libzmq.dll`: With Python (but Lua also needs it)

**Rationale:** `bin/pollnet/` already contains network-related DLLs (pollnet itself). Lua FFI can load from there. Centralizes network dependencies.

### D7: Error Handling Strategy

**Decision:** Graceful degradation with logging

- If ZMQ init fails: Log warning, disable publishing, game continues
- If Python service is down: Messages dropped silently, game continues
- If message malformed: Log error, skip message, continue processing

**Rationale:** Game stability is paramount. ZMQ communication is "best effort" in Phase 1. Users should never experience game crashes due to Python service issues.

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| libzmq.dll compatibility issues | Lua ZMQ init fails | Test on multiple Windows versions; fallback to disabled state |
| ZMQ port conflicts | Service can't bind | Configurable port in MCM; clear error message |
| Message loss under load | Events dropped | Acceptable in Phase 1 (logging only); add HWM in Phase 2 |
| lzmq FFI not available | ZMQ bridge fails | Detect LuaJIT vs Lua 5.1 at init; graceful fallback |
| Python service crashes | No event logging | Game unaffected; add supervisor/restart in Phase 2 |

## Migration Plan

### Deployment Steps

1. **Add Python service files** - No game impact
2. **Add libzmq.dll** - No game impact (not loaded yet)
3. **Add Lua ZMQ bridge module** - Loaded but not called
4. **Add parallel publish calls** - Events flow to Python
5. **Add MCM config sync** - Config flows to Python
6. **Add game load sync** - Full config on load

### Rollback Strategy

All changes are additive. To rollback:
1. Remove ZMQ publish calls from `trigger.lua`
2. Remove MCM callback from `talker_mcm.script`
3. Remove persistence callback from `talker_game_persistence.script`
4. Optionally delete new files (not required for rollback)

Game will function normally without Python service at any point.

## Open Questions

1. **ZMQ High Water Mark:** Should we set a message buffer limit in Phase 1, or defer to Phase 2?
2. **Heartbeat interval:** 5 seconds proposed - is this appropriate for detecting service availability?
3. **Config sync timing:** Should we delay config sync after game load (MCM may not be fully initialized)?
