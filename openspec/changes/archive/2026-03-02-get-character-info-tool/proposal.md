## Why

The ConversationManager's tool loop (from the `llm-tool-calling-infrastructure` change) supports `get_memories` and `background`, but cannot query full character details + squad composition. When the LLM picks a speaker, it has no way to discover squad mates, generate connected backstories, or determine gender for generic NPCs. The `get_character_info` tool (Tool 3 in the design doc) fills this gap — it returns character info with gender and squad members, triggers squad discovery side-effects (memory entry creation + global backfill), and provides the context needed for background generation.

## What Changes

- Add `get_character_info` LLM tool definition to the ConversationManager's TOOLS list (takes `character_id`, returns character + squad_members with gender and background)
- Add `query.character_info` Lua resource handler in `talker_ws_query_handlers.script` that fetches character data, derives gender from `sound_prefix`, resolves squad members, and includes backgrounds from memory store
- Add squad discovery side-effect: when `query.character_info` is processed, Lua creates memory entries for squad members not yet in `memory_store` and backfills from `global_event_buffer`
- Add `_handle_get_character_info` Python handler in ConversationManager that dispatches `query.character_info` via state query client and formats the response for the LLM
- Wire `serialize_character_info` in `bin/lua/infra/ws/serializer.lua` for the extended response format (character + squad members + gender + background)

## Capabilities

### New Capabilities
- `get-character-info-tool`: LLM tool that returns detailed character info including gender, background, and squad member discovery. Covers the tool definition, Lua query handler, Python tool handler, serialization, and squad discovery side-effects.

### Modified Capabilities
- `tool-based-dialogue`: Adds `get_character_info` as a third tool to the ConversationManager's tool set (alongside `get_memories` and `background`). Updates tool instructions in the system prompt.
- `lua-state-query-handler`: Adds `query.character_info` resource to the resource registry with squad resolution + memory entry creation side-effects.

## Impact

- **Python** (`dialogue/conversation.py`): New tool definition, handler method, updated TOOLS list and system prompt
- **Lua** (`talker_ws_query_handlers.script`): New `query.character_info` resource handler with squad resolution
- **Lua** (`bin/lua/infra/ws/serializer.lua`): New `serialize_character_info` function for extended character + squad format with gender field
- **Lua** (`talker_game_queries.script`): May need new `get_squad_members(character)` helper if existing `get_squad()` is insufficient
- **Lua** (`bin/lua/domain/repo/memory_store_v2.lua`): Squad discovery path uses existing `create_entry` + backfill-globals logic
- **No wire protocol changes**: Uses existing `state.query.batch` mechanism, just adds a new resource name
- **No breaking changes**: Additive — existing `get_memories` and `background` tools unchanged
