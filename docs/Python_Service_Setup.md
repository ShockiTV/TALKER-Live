# TALKER Expanded - Python Service Setup



## Overview



**Starting from Phase 2, the Python service is REQUIRED for TALKER Expanded to generate AI dialogue.** This is a breaking change from previous versions.



The Python service handles:

- All LLM calls for dialogue generation

- Speaker selection (choosing which NPC responds)

- Memory compression and long-term memory updates

- Prompt building and context management



Benefits of this architecture:

- Non-blocking game performance (AI processing happens in a separate process)

- Faster response times via async Python HTTP clients

- Future integration with local LLMs

- Advanced memory management and prompt optimization

- Better error handling and retry logic



## Requirements



- Python 3.10 or higher

- 4GB RAM minimum (8GB recommended for local models)

- Windows 10/11

- ~100MB disk space for dependencies



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



### 3. Start the Game



1. Launch STALKER Anomaly

2. Load a save - dialogue will be generated via the Python service



**Note:** The Python service is always enabled. No MCM toggle is needed.



## Usage



### Starting the Service



1. Run `launch_talker_service.bat` **before** starting the game

2. Start STALKER Anomaly

3. Load a save - dialogue will be generated via the Python service



**IMPORTANT:** The game will NOT generate any AI dialogue if the Python service is not running.



### Checking Health



The service exposes a health endpoint:

- Open browser to `http://localhost:5557/health`

- You should see: `{"status": "ok", "ws_connected": true, ...}`



### Debug Endpoints



- `http://localhost:5557/debug/config` - View current mirrored MCM config



### Logs



Service logs are written to `talker_service/logs/` directory.



## Configuration



### Environment Variables



Create a `.env` file in `talker_service/` (copy from `.env.example`):



```env

# WebSocket Settings

WS_HOST=127.0.0.1

WS_PORT=5557



# Token Authentication (optional, for remote/hosted deployments)

# Format: name1:token1,name2:token2

# When unset, all connections are accepted (local mode).

TALKER_TOKENS=



# FastAPI Settings

HTTP_HOST=127.0.0.1

HTTP_PORT=8080



# LLM Settings

DEFAULT_LLM_PROVIDER=openai

LLM_TIMEOUT=60.0

STATE_QUERY_TIMEOUT=30.0



# Logging

LOG_LEVEL=INFO

LOG_FILE=logs/talker_service.log

```



### MCM Settings



Use the Connection tab in MCM to control local-vs-remote behavior:

| Setting | Description | Default |
|---------|-------------|---------|
| Service Type | `Local` connects directly to local Python service; `Remote` derives URL from hub + branch | `Local` |
| Service Hub URL | Remote hub domain used to derive `wss://.../ws/<branch>` | empty |
| Branch | Remote branch selector (`main`, `dev`, `custom`) | `main` |
| Custom Branch | Branch name used when Branch=`custom` | empty |
| Service URL | Explicit local WS URL override | empty |
| Service WS Port | Local WS port used when Service URL is empty | 5557 |
| Auth Username / Password | Keycloak credentials used for remote ROPC token exchange | empty |
| Auth Client ID | Keycloak client ID for token exchange | `talker-client` |
| Auth Client Secret | Keycloak client secret (if required) | empty |
| WS Token | Optional static fallback token when username/password are empty | empty |
| LLM Timeout | Max seconds per LLM request | 60 |
| State Query Timeout | Max seconds for Lua state queries | 10 |

### SERVICE_HUB_URL Derivation

When `SERVICE_HUB_URL` is set in `.env`, Python derives service endpoints automatically **only when explicit per-service URLs are not configured**:

- `tts_service_url = {SERVICE_HUB_URL}/api/tts`
- `stt_endpoint = {SERVICE_HUB_URL}/api/stt/v1`
- `ollama_base_url = {SERVICE_HUB_URL}/api/embed`

Precedence order:

1. Explicit per-service URLs (`TTS_SERVICE_URL`, `STT_ENDPOINT`, `OLLAMA_BASE_URL`)
2. MCM `service_hub_url` (from `config.sync`)
3. `.env` `SERVICE_HUB_URL`

This lets local Python consume VPS-hosted shared services while still allowing advanced overrides.

### Local Python + Remote Shared Services

1. Start local Python service as usual (`launch_talker_service.bat`).
2. In MCM Connection tab, set `Service Type = Remote`.
3. Set `Service Hub URL` to your VPS domain (for example `https://talker-live.duckdns.org`).
4. Choose `Branch` (`main`, `dev`, or `custom`).
5. Enter Keycloak `Auth Username` / `Auth Password` (and client credentials if required).
6. Keep `Service URL` empty unless you need a direct override.

Lua then connects to derived WS URL (`wss://<hub>/ws/<branch>`), while Python can call remote TTS/STT/embed APIs through the authenticated gateway routes.



## Troubleshooting



### Service Won't Start



1. Check Python is installed: `python --version`

2. Check port is not in use: `netstat -an | findstr :5557`

3. Check logs in `talker_service/logs/`



### Game Doesn't Connect



1. Ensure service is running **before** loading a save

2. Verify ports match in MCM and `.env`

3. Check `logs/talker_debug.log` for WebSocket connection errors

4. A HUD notification will appear if the service is disconnected



### No Dialogue Generated



1. Verify Python service is running and connected (check /health endpoint)

2. Check service logs for LLM errors

3. Verify your API keys are correctly configured



### Conversation Growing Too Large



If you see "Pruning conversation" in the logs frequently, the context window is being managed automatically. This is normal for long play sessions. If you experience issues:

1. Check logs for `Pruning conversation: X tokens > Y threshold` messages
2. The service automatically prunes to 50% of context when reaching 75% capacity (96k/128k tokens)
3. System prompts and recent dialogue are always preserved
4. To disable pruning, set `ENABLE_CONTEXT_PRUNING=false` in `.env`
5. To disable conversation persistence entirely, set `ENABLE_CONVERSATION_PERSISTENCE=false`



## Conversation Persistence



Each connected game session maintains its own persistent conversation history with the LLM. This means NPCs retain context from previous events within the same session — the LLM remembers what dialogue it generated earlier and can reference past interactions.



### How It Works



- When a game connects via WebSocket, a **per-session LLM client** is created
- Each event (death, artifact found, etc.) appends messages to the session's conversation
- The LLM sees the full conversation history, enabling it to generate more contextual dialogue
- When the session disconnects (game closes), the conversation is discarded



### Context Window Management



The LLM has a finite context window (128k tokens for GPT-4o). To prevent exceeding it:

- **Threshold**: At 75% capacity (~96k tokens), automatic pruning triggers
- **Target**: Conversation is pruned down to 50% capacity (~64k tokens)
- **Priority**: System prompts and recent messages are always kept; older dialogue and tool results are removed first

Pruning events are logged at INFO level in the service logs.



### Feature Flags



| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `ENABLE_CONVERSATION_PERSISTENCE` | Keep conversation history across events | `true` |
| `ENABLE_CONTEXT_PRUNING` | Auto-prune when context window fills up | `true` |



## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    STALKER Anomaly (Lua)                    │
├─────────────────────────────────────────────────────────────┤
│  talker_ws_integration.script                               │
│    └─► infra/bridge/channel.lua (WebSocket via pollnet)      │
│                              │                               │
│                         pollnet.dll                         │
└──────────────────────────────┼──────────────────────────────┘
                               │ WebSocket (ws:5557)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              talker_service (AI processing + TTS)          │
├─────────────────────────────────────────────────────────────┤
│  Dialogue generation, memory compression, speaker selection │
│  TTS audio generation and streaming                          │
│  Speech-to-text via native microphone DLL                    │
└─────────────────────────────────────────────────────────────┘
```
┌─────────────────────────────────────────────────────────────┐
│                   talker_service (Python)                   │
├─────────────────────────────────────────────────────────────┤
│  WSRouter (FastAPI WebSocket endpoint at /ws)               │
│    └─► handlers/events.py (game events → dialogue)          │
│    └─► handlers/audio.py (mic.audio.chunk → STT)            │
│    └─► handlers/config.py (config sync)                     │
│                                                             │
│  FastAPI (http:5557)                                        │
│    └─► /ws (WebSocket endpoint)                              │
│    └─► /health (health check)                               │
│    └─► /debug/config (view current config)                  │
└─────────────────────────────────────────────────────────────┘
```

## Service Status Notifications



The game will show HUD notifications if the Python service becomes unavailable:



- **"TALKER: Python service not responding. AI dialogue disabled."** - Shown when the service hasn't responded for 15 seconds

- **"TALKER: Python service reconnected. AI dialogue restored."** - Shown when connection is restored



This helps you know if you forgot to start the service or if it crashed.
