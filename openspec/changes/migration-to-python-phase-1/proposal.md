## Why

The current architecture has all AI logic (LLM calls, prompt building, memory compression) in Lua, which is difficult to test, debug, and extend. Python offers better tooling, async support, and library ecosystem for AI workloads. Phase 1 establishes the communication infrastructure between Lua (thin client) and Python (compute service) without breaking existing functionality.

## What Changes

- **Add ZeroMQ-based IPC layer** between Lua game client and Python service
- **Add Python service skeleton** using FastAPI + pyzmq that receives and logs game events
- **Add parallel event publishing** from Lua triggers (existing flow unchanged)
- **Add MCM config sync** to Python service when settings change in-game
- **Add config sync on game load** to ensure Python service has current settings
- **Add health check / heartbeat** mechanism between Lua and Python

## Capabilities

### New Capabilities

- `lua-zmq-bridge`: ZeroMQ connection manager for Lua side - initializes PUB socket, provides publish function, handles connection errors gracefully
- `lua-event-publisher`: Publishes game events to ZMQ topics in parallel with existing event flow (fire-and-forget, non-blocking)
- `lua-config-sync`: Publishes full MCM config on settings change and game load
- `python-zmq-router`: FastAPI-based Python service with ZMQ SUB socket, topic-based handler registry, async message processing
- `python-config-mirror`: Receives and stores MCM config updates from Lua, makes config available to other Python modules

### Modified Capabilities

- `talker-mcm`: Add callback to publish config changes via ZMQ
- `talker-persistence`: Add config sync trigger on game load

## Impact

### New Dependencies
- **Lua**: lzmq (LuaJIT FFI binding) + libzmq.dll in game bin folder
- **Python**: pyzmq, fastapi, uvicorn, pydantic, loguru, python-dotenv

### New Files
```
talker_service/                    # Root level (same as mic_python)
├── pyproject.toml
├── requirements.txt
├── run.py
└── src/talker_service/
    ├── __init__.py
    ├── __main__.py
    ├── config.py
    ├── transport/
    │   └── router.py
    ├── handlers/
    │   ├── events.py
    │   └── config.py
    └── models/
        ├── messages.py
        └── config.py

bin/lua/infra/zmq/
├── bridge.lua
└── publisher.lua

bin/pollnet/                       # libzmq.dll location
└── libzmq.dll
```

### Modified Files
- `gamedata/scripts/talker_mcm.script` - Add config change callback
- `gamedata/scripts/talker_game_persistence.script` - Add config sync on load
- `bin/lua/interface/trigger.lua` - Add parallel ZMQ publish

### Risk Mitigation
- All changes are additive - existing Lua flow continues to work
- If ZMQ unavailable, Lua logs warning and continues without publishing
- If Python service is down, game runs normally (fire-and-forget publishing)
- Easy rollback: remove ZMQ publish calls, delete new files
