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
| Domain | `bin/lua/domain/` | Core entities (`Character`, `Event`), repositories (`memory_store`, `event_store`), domain data tables (`domain/data/`), and domain services (`domain/service/`) |
| Framework | `bin/lua/framework/` | Utilities (logger, inspect, `utils.lua`) — no game dependencies |
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
│   │   ├── models.py           # Prompt-specific models
│   │   └── lookup.py           # resolve_personality() and resolve_backstory() for ID→text lookup
│   ├── texts/                  # Text lookup modules (dict constants)
│   │   ├── personality/        # Personality texts (bandit.py with TEXTS dict, etc.)
│   │   └── backstory/          # Backstory texts (unique.py, generic.py, etc.)
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
- **OpenSpec**: Experimental workflow for structured changes (`openspec/`). **IMPORTANT**: Use the globally installed `openspec` CLI directly (e.g., `openspec status`, `openspec list --json`). Do NOT run it via `python -m openspec` or through a venv — it is a global install.
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
| `state.query.batch` | Batch state query (multiple sub-queries in one roundtrip) |
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

### 5a. Engine Facade (Required for all `bin/lua/` Code)

`bin/lua/` modules **must never** access STALKER engine globals directly (`talker_mcm`, `talker_game_queries`, `talker_game_commands`, `talker_game_async`, `talker_game_files`, `ini_file`, `printf`, `CreateTimeEvent`, etc.). Always go through the engine facade:

```lua
local engine = require("interface.engine")

-- Read MCM config value (falls back to config_defaults if MCM not loaded)
local val = engine.get_mcm_value("debug_logging")

-- Game queries
local name = engine.get_name(character)
local alive = engine.is_alive(character)

-- Game commands
engine.display_message(speaker, message, time)

-- Async / time events
engine.create_time_event("my_event", key, 0, handler)
```

This makes all `bin/lua/` modules **testable without a running game** — just inject `mock_engine`:
```lua
-- In any test file, before requiring any bin/lua module:
require("tests.test_bootstrap")  -- wires mock_engine automatically
```

**Tests must require `tests.test_bootstrap` as their first line** (after `package.path`) to inject the mock engine before any `bin/lua/` module loads. Use `mock_engine._set(key, value)` to override return values per test.

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
**IMPORTANT**: Always use the `lua-tests` MCP server tools to run Lua tests — do NOT call `lua5.1` directly in the terminal.

| MCP Tool | Purpose |
|----------|---------|
| `list_tests` | Discover all `test_*.lua` files (optionally filter by `path`) |
| `run_tests` | Run tests by path/pattern; accepts `path`, `pattern`, `fail_fast`, `include_live` |
| `run_single_test` | Run one test file with full output |
| `get_last_run_results` | Read results from the most recent run |

**Examples**:
- All tests: `run_tests {}` (no args)
- By subdirectory: `run_tests { path: "tests/domain/" }`
- By pattern: `run_tests { pattern: "serializer" }`
- Single file: `run_single_test { file: "tests/domain/data/test_mutant_names.lua" }`
- List tests: `list_tests { path: "tests/domain/" }`

**Manual fallback** (if MCP unavailable): `lua5.1.exe tests/<path>/test_<module>.lua`
- Note: Use `lua5.1.exe`, not `lua` (which may not be in PATH)
- Test structure mirrors source: `tests/domain/`, `tests/infra/`, `tests/entities/`, etc.
- Use mocks from `tests/mocks/` (mock_characters, mock_game_adapter, mock_REST)
- Live integration tests in `tests/live/` (require actual LLM API keys; excluded by default from MCP tools)

### Python Tests
**IMPORTANT**: Always use the `talker-tests` MCP server tools to run Python tests — do NOT call `python`, `pytest`, or `.venv` directly in the terminal.

| MCP Tool | Purpose |
|----------|---------|
| `list_tests` | Discover all test node IDs (optionally filter by `path`) |
| `run_tests` | Run tests by path/pattern; accepts `path`, `pattern`, `verbose`, `fail_fast` |
| `run_single_test` | Run one test by full node ID with detailed traceback |
| `get_last_run_results` | Read results from the most recent run |
| `get_captured_payloads` | Inspect ZMQ/HTTP wire payloads from e2e tests |
| `get_test_source` | Read source of a specific test function |

**Examples**:
- All tests: `run_tests {}` (no args)
- E2E only: `run_tests { path: "tests/e2e/" }`
- Integration only: `run_tests { path: "tests/integration/" }`
- By pattern: `run_tests { pattern: "test_dialogue" }`
- Single: `run_single_test { node_id: "tests/e2e/test_scenarios.py::test_e2e_scenario[death_wolf_full]" }`

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
- [`bin/lua/domain/data/unique_npcs.lua`](bin/lua/domain/data/unique_npcs.lua) - Set of ~130 story NPC IDs; `is_unique(name)` predicate
- [`bin/lua/domain/data/mutant_names.lua`](bin/lua/domain/data/mutant_names.lua) - Ordered pattern→display-name map; `describe(tech_name)` → `"a DisplayName"`
- [`bin/lua/domain/data/ranks.lua`](bin/lua/domain/data/ranks.lua) - Rank values, reputation tiers, `format_character_info(char)` formatting
- [`bin/lua/domain/service/cooldown.lua`](bin/lua/domain/service/cooldown.lua) - Generic `CooldownManager` used by all 5 trigger scripts; supports named slots + anti-spam
- [`bin/lua/domain/service/importance.lua`](bin/lua/domain/service/importance.lua) - Pure `is_important_person(flags)` predicate
- [`bin/lua/infra/zmq/serializer.lua`](bin/lua/infra/zmq/serializer.lua) - Wire-format serialization (character, context, event, events list)
- [`bin/lua/interface/world_description.lua`](bin/lua/interface/world_description.lua) - Pure string assembly for world context (`build_description`, `time_of_day`, etc.)
- [`bin/lua/framework/utils.lua`](bin/lua/framework/utils.lua) - Common utilities: `must_exist`, `try`, `join_tables`, `Set`, `shuffle`, `safely`, `array_iter`
- [`bin/lua/interface/config.lua`](bin/lua/interface/config.lua) - MCM config getters, default settings
- [`bin/lua/interface/trigger.lua`](bin/lua/interface/trigger.lua) - Event triggering API
- [`gamedata/scripts/talker_game_queries.script`](gamedata/scripts/talker_game_queries.script) - Game state queries (delegates extracted logic to `bin/lua/` modules)
- [`gamedata/scripts/talker_zmq_integration.script`](gamedata/scripts/talker_zmq_integration.script) - ZMQ lifecycle, event publishing
- [`gamedata/scripts/talker_zmq_command_handlers.script`](gamedata/scripts/talker_zmq_command_handlers.script) - Handles commands from Python
- [`gamedata/scripts/talker_zmq_query_handlers.script`](gamedata/scripts/talker_zmq_query_handlers.script) - State query handlers (serialization delegated to `infra.zmq.serializer`)

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
- [`docs/zmq-api.yaml`](docs/zmq-api.yaml) - ZMQ API contract (single source of truth for wire protocol)
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
