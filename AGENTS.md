# AGENTS.md

## Project Overview

**TALKER Expanded** is a STALKER: Anomaly mod that enables AI-powered NPC dialogue using Large Language Models (LLMs). It implements a hierarchical memory system where NPCs witness events, store memories, and generate contextual dialogue through AI models.

This is a **dual-codebase project**:
- **Lua** (game integration) - Runs inside the STALKER: Anomaly game engine
- **Python** (AI processing & microphone input) - Runs as a standalone service

**Phase 2+ Architecture**: AI dialogue generation is handled by the Python service, NOT Lua. The game (Lua) stores events and sends them via ZeroMQ to Python, which handles LLM calls, speaker selection, and memory compression.

## Architecture

### Clean Architecture Pattern (Lua)

The Lua codebase follows clean architecture with strict layer separation:

| Layer | Path | Purpose |
|-------|------|---------|
| Application | `bin/lua/app/` | Orchestrates event registration (e.g., `talker.lua`) |
| Domain | `bin/lua/domain/` | Core entities (`Character`, `Event`) and repositories (`memory_store`, `event_store`, `personalities`, `backstories`) |
| Framework | `bin/lua/framework/` | Utilities (logger, inspect) - no game dependencies |
| Infrastructure | `bin/lua/infra/` | External integrations: HTTP, ZMQ, AI utilities, STALKER game data |
| Interface | `bin/lua/interface/` | Bridge layer (`config.lua` reads MCM settings, `interface.lua` exposes public API) |

**Critical Rule**: `bin/lua/` code must NEVER directly call STALKER game APIs - always go through `talker_game_*` adapters in `gamedata/scripts/`.

### Game Scripts (`gamedata/scripts/`)

- `talker_game_*.script` - Game adapters (queries, commands, persistence, async)
- `talker_trigger_*.script` - Event triggers (death, injury, artifact, etc.)
- `talker_listener_*.script` - Event listeners that register events with the talker system
- `talker_input_*.script` - Player input handlers (chatbox, microphone)
- `talker_zmq_*.script` - ZMQ integration (query handlers, command handlers)
- `talker_mcm.script` - MCM (Mod Configuration Menu) UI

### Python Service Architecture (`talker_service/`)

```
talker_service/
├── run.py                      # Entry point (Windows asyncio fix)
├── src/talker_service/
│   ├── __main__.py             # FastAPI app + ZMQ router lifecycle
│   ├── config.py               # Service configuration (pydantic-settings)
│   ├── models/
│   │   ├── messages.py         # Pydantic schemas for ZMQ messages
│   │   └── config.py           # MCM config mirror schema
│   ├── llm/                    # LLM client implementations
│   │   ├── factory.py          # get_llm_client(model_method, ...)
│   │   ├── base.py             # LLMClient Protocol and BaseLLMClient
│   │   ├── models.py           # Message and LLMOptions models
│   │   ├── openai_client.py    # OpenAI client (model_method=0)
│   │   ├── openrouter_client.py# OpenRouter client (model_method=1)
│   │   ├── ollama_client.py    # Ollama client (model_method=2)
│   │   └── proxy_client.py     # Gemini proxy client (model_method=3)
│   ├── prompts/                # Prompt building
│   │   ├── dialogue.py         # Dialogue generation prompts
│   │   ├── speaker.py          # Speaker selection prompts
│   │   ├── memory.py           # Memory compression prompts
│   │   ├── builder.py          # Prompt building utilities
│   │   ├── factions.py         # Faction-specific prompt content
│   │   ├── helpers.py          # Prompt helper functions
│   │   └── models.py           # Prompt-specific models
│   ├── dialogue/               # Dialogue generation
│   │   ├── generator.py        # DialogueGenerator orchestrator
│   │   ├── speaker.py          # SpeakerSelector
│   │   └── cleaner.py          # Response cleaning utilities
│   ├── state/                  # Game state queries
│   │   ├── client.py           # StateQueryClient (ZMQ request/response)
│   │   └── models.py           # State query models
│   ├── transport/
│   │   └── router.py           # ZMQRouter (bidirectional PUB/SUB)
│   └── handlers/
│       ├── events.py           # Game event handlers (triggers dialogue)
│       └── config.py           # ConfigMirror class
└── tests/                      # pytest test suite (~130 tests)
```

### Communication Flow

```
Lua (Game)                          Python (Service)
    │                                     │
    │  ZMQ PUB (5555)  ─────────────────► │  SUB
    │  game.event, player.dialogue, etc.  │
    │                                     │
    │  ZMQ SUB (5556)  ◄────────────────  │  PUB
    │  dialogue.display, memory.update    │
    │                                     │
    │  HTTP 8080/health  ───────────────► │  FastAPI
```

## Technologies

### Lua Stack
- **Language**: Lua 5.1 (LuaJIT in STALKER Anomaly)
- **HTTP Client**: pollnet FFI bindings
- **Message Queue**: ZeroMQ via LuaJIT FFI to libzmq.dll
- **Serialization**: Custom JSON library (`bin/lua/infra/HTTP/json.lua`)

### Python Stack
- **Language**: Python 3.10+
- **Web Framework**: FastAPI + Uvicorn
- **Message Queue**: pyzmq (ZeroMQ)
- **Data Validation**: Pydantic v2 + pydantic-settings
- **Logging**: loguru
- **Configuration**: python-dotenv
- **Testing**: pytest + pytest-asyncio
- **LLM Clients**: OpenAI API, OpenRouter, Ollama, Custom Proxy

### Project Structure
- **OpenSpec**: Experimental workflow for structured changes (`openspec/`)
- **Kilocode**: `.kilocode/` directory with skills and configuration

## Key Patterns & Conventions

### 1. Typed Event System

Events flow through the system:
```
Game → Trigger → trigger.talker_event_near_player() → Listener → 
talker.register_event() → Event Store → ZMQ → Python → AI Dialogue → 
ZMQ → Lua → Display
```

**Creating typed events** (preferred):
```lua
local EventType = require("domain.model.event_types")
local trigger = require("interface.trigger")

-- In a trigger script:
local context = { actor = player_character, victim = target_character }
trigger.talker_event_near_player(EventType.DEATH, context, true, { is_silent = false })
```

**EventType enum** (`bin/lua/domain/model/event_types.lua`):
- `DEATH`, `DIALOGUE`, `CALLOUT`, `TAUNT`, `ARTIFACT`, `ANOMALY`
- `MAP_TRANSITION`, `EMISSION`, `INJURY`, `SLEEP`, `TASK`
- `WEAPON_JAM`, `RELOAD`, `IDLE`, `ACTION`

### 2. Memory Architecture (Three-Tier System)

- **Recent Events** (last ~12 events): Raw events stored in `event_store`
- **Mid-Term Memory** (previous ~12 events): Auto-compressed summary (~900 chars)
- **Long-Term Memory** (persistent, max 6400 chars): Updated via LLM calls in `memory_store:update_narrative()`

Compression triggers when event count exceeds `COMPRESSION_THRESHOLD` (12 events).

### 3. ZMQ Communication Pattern

All messages use: `<topic> <json-payload>`

**Lua → Python Topics**:
| Topic | Purpose |
|-------|---------|
| `game.event` | Game events (death, dialogue, artifacts, etc.) |
| `player.dialogue` | Player chatbox input |
| `player.whisper` | Player whisper input (companion-only) |
| `config.update` | MCM setting changed |
| `config.sync` | Full config on game load |
| `system.heartbeat` | Connection health check |

**Python → Lua Topics**:
| Topic | Purpose |
|-------|---------|
| `dialogue.display` | Display dialogue for an NPC |
| `memory.update` | Update character's long-term memory |
| `state.query` | Request game state from Lua |
| `state.response` | Response to state query |

### 4. Error Handling

All game callbacks MUST be wrapped in error handlers:

```lua
local function safely(func, name)
    return function(...)
        local status, result = pcall(func, ...)
        if not status then log.error(name .. " failed: " .. result) end
        return result
    end
end
RegisterScriptCallback("actor_on_death", safely(on_death, "on_death"))
```

### 5. Package Path Management

Every Lua file accessing `bin/lua/` modules must start with:
```lua
package.path = package.path .. ";./bin/lua/?.lua;"
```

### 6. Configuration Access

Always use getters from `interface.config`, never access MCM directly from `bin/lua/`:
```lua
local config = require("interface.config")
local cooldown = config.idle_conversation_cooldown() * 1000 -- ms
```

### 7. LLM Client API

All LLM clients' `complete()` method returns a **string** directly, NOT an object with `.content`:

```python
# Correct:
response = await llm_client.complete(messages)
text = response  # response IS the string

# WRONG (old pattern):
text = response.content  # AttributeError!
```

### 8. Config Field Mappings

Lua MCM keys differ from Python model fields:

| Lua (MCM) Key | Python Field |
|---------------|--------------|
| `ai_model_method` | `model_method` |
| `custom_ai_model` | `model_name` |
| `custom_ai_model_fast` | `model_name_fast` |

### 9. Async Event Handling

Event handlers must NOT block the message loop. Use `asyncio.create_task()` for long-running operations:

```python
# Correct:
asyncio.create_task(_handle_event_async(event))

# WRONG (causes deadlock):
await _handle_event_async(event)
```

## Testing

### Lua Tests
- **Run**: `lua5.1.exe tests/<path>/test_<module>.lua` (uses LuaUnit)
- Note: Use `lua5.1.exe`, not `lua` (which may not be in PATH)
- Test structure mirrors source: `tests/domain/`, `tests/infra/`, `tests/entities/`, etc.
- Use mocks from `tests/mocks/` (mock_characters, mock_game_adapter, mock_REST)
- Live integration tests in `tests/live/` (require actual LLM API keys)

### Python Tests
**IMPORTANT**: Must use the virtual environment, not system Python

**Run all tests**:
```powershell
cd talker_service
.\.venv\Scripts\activate
python -m pytest tests/ -v
```

Or as one-liner:
```powershell
cd talker_service; .\.venv\Scripts\activate; python -m pytest tests/ -v --tb=short
```

**First-time setup** (if `.venv` doesn't exist):
```powershell
cd talker_service
python -m venv .venv
.\.venv\Scripts\activate
pip install -e ".[dev]"
```

## Common Tasks

### Adding a New Trigger

1. Create `talker_trigger_<event>.script`
2. Implement condition check
3. Create event with `game.create_event()`
4. Call `trigger.register_near_player()`

See [`gamedata/scripts/talker_trigger_artifact.script`](gamedata/scripts/talker_trigger_artifact.script) for a simple example.

### Adding an AI Provider (LLM Client)

1. Create module in `talker_service/src/talker_service/llm/`
2. Implement `BaseLLMClient` interface with `complete(messages, **kwargs) -> str`
3. Register in `llm/factory.py`

### Modifying Prompts

Edit files in `talker_service/src/talker_service/prompts/`:
- `dialogue.py` - Dialogue generation prompts
- `speaker.py` - Speaker selection prompts
- `memory.py` - Memory compression prompts

### Debugging

**Lua side**:
- Check `logs/talker_debug.log` (not console - console only shows warnings/errors)
- Enable verbose logging in MCM

**Python side**:
- Check `talker_service/logs/talker_service.log`
- Use health endpoint: `http://localhost:8080/health`
- Use debug endpoint: `http://localhost:8080/debug/config`

## Critical Files to Reference

### Lua (Game Integration)
- [`bin/lua/app/talker.lua`](bin/lua/app/talker.lua) - Event registration, bypasses AI when Python service enabled
- [`bin/lua/domain/model/event.lua`](bin/lua/domain/model/event.lua) - Event entity and TEMPLATES
- [`bin/lua/domain/model/event_types.lua`](bin/lua/domain/model/event_types.lua) - EventType enum
- [`bin/lua/domain/repo/memory_store.lua`](bin/lua/domain/repo/memory_store.lua) - Memory storage
- [`bin/lua/interface/config.lua`](bin/lua/interface/config.lua) - MCM config getters, default settings
- [`bin/lua/interface/trigger.lua`](bin/lua/interface/trigger.lua) - Event triggering API
- [`gamedata/scripts/talker_game_queries.script`](gamedata/scripts/talker_game_queries.script) - Game state queries
- [`gamedata/scripts/talker_zmq_integration.script`](gamedata/scripts/talker_zmq_integration.script) - ZMQ lifecycle, event publishing
- [`gamedata/scripts/talker_zmq_command_handlers.script`](gamedata/scripts/talker_zmq_command_handlers.script) - Handles commands from Python

### Python (AI Processing)
- [`talker_service/src/talker_service/__main__.py`](talker_service/src/talker_service/__main__.py) - FastAPI app and ZMQ router
- [`talker_service/src/talker_service/dialogue/generator.py`](talker_service/src/talker_service/dialogue/generator.py) - Dialogue generation orchestrator
- [`talker_service/src/talker_service/dialogue/speaker.py`](talker_service/src/talker_service/dialogue/speaker.py) - Speaker selection
- [`talker_service/src/talker_service/prompts/dialogue.py`](talker_service/src/talker_service/prompts/dialogue.py) - Dialogue prompt building
- [`talker_service/src/talker_service/prompts/memory.py`](talker_service/src/talker_service/prompts/memory.py) - Memory compression prompts
- [`talker_service/src/talker_service/llm/factory.py`](talker_service/src/talker_service/llm/factory.py) - LLM client factory
- [`talker_service/src/talker_service/transport/router.py`](talker_service/src/talker_service/transport/router.py) - ZMQ router
- [`talker_service/src/talker_service/handlers/events.py`](talker_service/src/talker_service/handlers/events.py) - Event handlers
- [`talker_service/src/talker_service/state/client.py`](talker_service/src/talker_service/state/client.py) - State query client

### Documentation
- [`docs/Python_Service_Setup.md`](docs/Python_Service_Setup.md) - Detailed setup instructions
- [`docs/ZMQ_Message_Schema.md`](docs/ZMQ_Message_Schema.md) - ZMQ message format specification
- [`docs/Memory_Compression.md`](docs/Memory_Compression.md) - Memory system documentation

## External Documentation

- See [`.github/copilot-instructions.md`](.github/copilot-instructions.md) for additional AI coding agent instructions
- See [`README.md`](README.md) for user-facing documentation and model recommendations

## Python Microphone System

Located in `mic_python/python/`:
- `main.py` - Watchdog-based file polling system
- `recorder.py` - Audio capture using sounddevice
- `whisper_api.py` / `whisper_local.py` - Transcription providers
- Communicates via temp files (`talker_mic_io_commands`, `talker_mic_io_transcription`)

Launch via `launch_mic.bat`, not directly.

## Launch Commands

**Python Service** (required for AI dialogue):
```batch
launch_talker_service.bat
```

**Microphone** (optional):
```batch
launch_mic.bat
```

**Game Launch** (IMPORTANT: Launch directly from MO2, NOT via Anomaly Launcher):
```
Anomaly.exe
```
