# TALKER Expanded - AI Coding Agent Instructions

## Project Overview

TALKER Expanded is a STALKER: Anomaly mod that enables AI-powered NPC dialogue using LLMs. It's a dual-codebase project: Lua (game integration) + Python (microphone input). The mod implements a hierarchical memory system where NPCs witness events, store memories, and generate contextual dialogue through AI models.

## Architecture (Clean Architecture Pattern)

The Lua codebase follows clean architecture with strict layer separation:

- **`bin/lua/app/`** - Application layer (e.g., `talker.lua` orchestrates dialogue generation)
- **`bin/lua/domain/`** - Core entities (`Character`, `Event`) and repositories (`memory_store`, `event_store`, `personalities`, `backstories`)
- **`bin/lua/framework/`** - Utilities (logger, inspect) - no game dependencies
- **`bin/lua/infra/`** - External integrations:
  - `AI/` - LLM providers (GPT, OpenRouter, Ollama, proxy)
  - `HTTP/` - Network layer using pollnet FFI bindings
  - `STALKER/` - Game-specific data (factions, locations, world_state)
- **`bin/lua/interface/`** - Bridge layer (`config.lua` reads MCM settings, `interface.lua` exposes public API)
- **`gamedata/scripts/`** - Game callbacks (STALKER X-Ray engine integration):
  - `talker_game_*.script` - Game adapters (queries, commands, persistence, async)
  - `talker_trigger_*.script` - Event triggers (death, injury, artifact, etc.)
  - `talker_listener_*.script` - Event listeners that register events with the talker system
  - `talker_input_*.script` - Player input handlers (chatbox, microphone)
  - `talker_mcm.script` - MCM configuration UI

**Critical Rule**: `bin/lua/` code must NEVER directly call STALKER game APIs - always go through `talker_game_*` adapters in `gamedata/scripts/`.

## Key Patterns & Conventions

### 1. Typed Event System (Core Workflow)

Events flow: Game → Trigger → `trigger.talker_event_near_player()` → Listener → `talker.register_event()` → Event Store → AI Speaker Selection → AI Dialogue Generation → Display

**Creating typed events** (preferred):
```lua
local EventType = require("domain.model.event_types")
local trigger = require("interface.trigger")

-- In a trigger script:
local context = { actor = player_character, victim = target_character }
trigger.talker_event_near_player(EventType.DEATH, context, true, { is_silent = false })
```

**Event structure** (typed):
- `type` - EventType enum value (DEATH, DIALOGUE, ARTIFACT, etc.)
- `context` - Table with event-specific fields (actor, victim, text, item_name, etc.)
- `game_time_ms`, `world_context`, `witnesses`, `flags`

**EventType enum** (see `bin/lua/domain/model/event_types.lua`):
`DEATH`, `DIALOGUE`, `CALLOUT`, `TAUNT`, `ARTIFACT`, `ANOMALY`, `MAP_TRANSITION`, `EMISSION`, `INJURY`, `SLEEP`, `TASK`, `WEAPON_JAM`, `RELOAD`, `IDLE`, `ACTION`

**Event templates** are defined in `bin/lua/domain/model/event.lua` TEMPLATES table - each EventType has a function that returns a format string and objects to interpolate.

**Key functions**:
- `Event.create(type, context, game_time_ms, world_context, witnesses, flags)` - Create typed event
- `Event.describe(event)` - Convert any event (typed or legacy) to human-readable text
- `Event.is_junk_event(event)` - Check if event is low-value for narrative (artifacts, anomalies, reloads, etc.)

### 2. Memory Architecture (Three-Tier System)

- **Recent Events** (last ~12 events): Raw events stored in `event_store`
- **Mid-Term Memory** (previous ~12 events): Auto-compressed summary
- **Long-Term Memory** (persistent, max 7000 chars): Updated via LLM calls in `memory_store:update_narrative()`

Memory compression triggers when event count exceeds `transformations.COMPRESSION_THRESHOLD`. See [bin/lua/infra/AI/transformations.lua](../bin/lua/infra/AI/transformations.lua) and [bin/lua/domain/repo/memory_store.lua](../bin/lua/domain/repo/memory_store.lua).

### 3. Callback-Based Async Pattern

All AI requests are asynchronous using callbacks (game loop integration):

```lua
AI_request.generate_dialogue(recent_events, function(speaker_id, dialogue, timestamp_to_delete)
    game_adapter.display_dialogue(speaker_id, dialogue)
    -- Update stores...
end)
```

Never use blocking operations. Use `talker_game_async.repeat_until_true()` for polling.

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

## Testing

- **Run tests**: `lua5.1.exe tests/<path>/test_<module>.lua` (uses LuaUnit)
  - Note: Use `lua5.1.exe`, not `lua` (which may not be in PATH)
  - Example: `lua5.1.exe tests/entities/test_event.lua`
- Test structure mirrors source: `tests/domain/`, `tests/infra/`, `tests/entities/`, etc.
- Use mocks from `tests/mocks/` (mock_characters, mock_game_adapter, mock_REST)
- Live integration tests in `tests/live/` (require actual LLM API keys)

## Critical Files to Reference

- [bin/lua/app/talker.lua](../bin/lua/app/talker.lua) - Main dialogue orchestration logic
- [bin/lua/domain/repo/memory_store.lua](../bin/lua/domain/repo/memory_store.lua) - Memory compression & retrieval
- [bin/lua/infra/AI/requests.lua](../bin/lua/infra/AI/requests.lua) - All AI request functions (dialogue, speaker selection, memory compression)
- [bin/lua/infra/AI/prompt_builder.lua](../bin/lua/infra/AI/prompt_builder.lua) - Prompt construction from game state
- [gamedata/scripts/talker_game_queries.script](../gamedata/scripts/talker_game_queries.script) - Game state queries (locations, characters, items)
- [gamedata/scripts/talker_game_persistence.script](../gamedata/scripts/talker_game_persistence.script) - Save/load system

## Common Tasks

**Adding a new trigger**: Create `talker_trigger_<event>.script`, implement condition check, create event with `game.create_event()`, call `trigger.register_near_player()`. See [gamedata/scripts/talker_trigger_artifact.script](../gamedata/scripts/talker_trigger_artifact.script) for a simple example.

**Adding AI provider**: Create module in `bin/lua/infra/AI/`, implement `send(messages, callback, opts)` interface, add to `requests.lua` model selection.

**Debugging dialogue**: Check `logs/talker_debug.log` (not console - console only shows warnings/errors). Enable verbose logging in MCM.

**Modifying prompts**: Edit `bin/lua/infra/AI/prompt_builder.lua` - dialogue prompts in `build_dialogue_request()`, memory compression in `build_compression_request()`.

## Python Microphone System

Located in `mic_python/python/`:
- `main.py` - Watchdog-based file polling system
- `recorder.py` - Audio capture using sounddevice
- `whisper_api.py` / `whisper_local.py` - Transcription providers
- Communicates via temp files (`talker_mic_io_commands`, `talker_mic_io_transcription`)

Launch via `launch_mic.bat`, not directly.