# TALKER Expanded - Python Service Setup

## Overview

The Python service is an **experimental** feature that allows TALKER Expanded to offload AI processing to a separate Python process. This enables:

- Faster dialogue generation using modern Python ML libraries
- Non-blocking game performance
- Future integration with local LLMs
- Advanced memory management and prompt optimization

## Requirements

- Python 3.10 or higher
- 4GB RAM minimum (8GB recommended for local models)
- Windows 10/11

## Installation

### 1. Install Python

Download and install Python from [python.org](https://python.org). Make sure to check "Add Python to PATH" during installation.

### 2. Install the Service

Run the launch script once to set up the virtual environment:

```batch
launch_talker_service.bat
```

This will:
1. Create a Python virtual environment in `talker_service/.venv`
2. Install all required dependencies
3. Start the service

### 3. Enable ZMQ in Game

1. Launch STALKER Anomaly
2. Open MCM (Mod Configuration Menu)
3. Navigate to **T.A.L.K.E.R. Expanded** → **Python Service (Experimental)**
4. Check **Enable ZMQ Publishing**
5. (Optional) Adjust the port if 5555 is already in use

## Usage

### Starting the Service

1. Run `launch_talker_service.bat` **before** starting the game
2. Start STALKER Anomaly
3. The service will receive game events and log them

### Checking Health

The service exposes a health endpoint:
- Open browser to `http://localhost:8080/health`
- You should see: `{"status": "healthy", ...}`

### Logs

Service logs are written to `talker_service/logs/` directory.

## Configuration

### Environment Variables

Create a `.env` file in `talker_service/` (copy from `.env.example`):

```env
# ZMQ Settings
LUA_PUB_ENDPOINT=tcp://127.0.0.1:5555

# FastAPI Settings
HTTP_HOST=127.0.0.1
HTTP_PORT=8080

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/talker_service.log
```

### MCM Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Enable ZMQ Publishing | Enables event publishing to Python service | Off |
| ZMQ Port | Port for ZeroMQ communication | 5555 |
| Heartbeat Interval | Seconds between heartbeat messages | 5 |

## Troubleshooting

### Service Won't Start

1. Check Python is installed: `python --version`
2. Check port is not in use: `netstat -an | findstr :5555`
3. Check logs in `talker_service/logs/`

### Game Doesn't Connect

1. Ensure service is running **before** loading a save
2. Check ZMQ is enabled in MCM
3. Verify ports match in MCM and `.env`
4. Check `logs/talker_debug.log` for ZMQ errors

### Missing libzmq.dll (Game Side)

The game (Lua) requires `libzmq.dll` in `bin/pollnet/`. The Python service does NOT need this file (pyzmq bundles its own library).

**Option 1: Download Pre-built**
1. Go to [ZeroMQ Windows releases](https://github.com/zeromq/libzmq/releases)
2. Download the latest `zeromq-*-win64.zip`
3. Extract `bin/libzmq-*.dll`
4. Rename to `libzmq.dll`
5. Place in `bin/pollnet/`

**Option 2: Use vcpkg**
```batch
vcpkg install zeromq:x64-windows
copy %VCPKG_ROOT%\installed\x64-windows\bin\libzmq*.dll bin\pollnet\libzmq.dll
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STALKER Anomaly (Lua)                    │
├─────────────────────────────────────────────────────────────┤
│  talker_zmq_integration.script                              │
│    └─► publisher.lua ──► bridge.lua (LuaJIT FFI)            │
│                              │                               │
│                         libzmq.dll                          │
└──────────────────────────────┼──────────────────────────────┘
                               │ ZMQ PUB/SUB (tcp:5555)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Python Service                            │
├─────────────────────────────────────────────────────────────┤
│  ZMQRouter (subscriber)                                     │
│    └─► handlers/events.py (game events)                     │
│    └─► handlers/config.py (config sync)                     │
│                                                             │
│  FastAPI (http:8080)                                        │
│    └─► /health (health check)                               │
│    └─► /debug/config (view current config)                  │
└─────────────────────────────────────────────────────────────┘
```

## Phase 1 Status (Current)

Phase 1 establishes the communication infrastructure:

- ✅ ZMQ bridge (Lua → Python)
- ✅ Event publishing (parallel to existing flow)
- ✅ Config sync
- ✅ Heartbeat system
- ✅ Health monitoring

**Note**: In Phase 1, the Python service only logs events. AI dialogue generation still happens in Lua via HTTP. Phase 2 will move AI processing to Python.

## Disabling the Service

To disable the Python service:

1. Uncheck "Enable ZMQ Publishing" in MCM
2. Stop the Python service (Ctrl+C in the terminal)

The game will continue to work normally using the existing Lua-based AI system.
