## 1. Lua Serialization (`bin/lua/infra/ws/serializer.lua`)

- [x] 1.1 Add `serialize_character_with_gender(char)` helper that calls `serialize_character(char)` and appends a `gender` field derived from `sound_prefix` (`"woman"` → `"female"`, otherwise → `"male"`)
- [x] 1.2 Add `serialize_character_info(char, squad_members, memory_store)` function that builds `{character: ..., squad_members: [...]}` using the gender helper and reading `background` from memory store for each character
- [x] 1.3 Add unit tests for `serialize_character_with_gender` — female sound_prefix, male sound_prefix, nil sound_prefix
- [x] 1.4 Add unit tests for `serialize_character_info` — single character no squad, character with squad, backgrounds present/absent

## 2. Lua Squad Resolution (`gamedata/scripts/talker_game_queries.script`)

- [x] 2.1 Add `get_squad_members(obj)` function that returns an array of Character objects for all squad members excluding the given character (wraps `get_squad()` + iteration)
- [x] 2.2 Handle edge cases: character not in squad (return `{}`), squad object nil, single-member squad

## 3. Lua Squad Discovery Side-Effect

- [x] 3.1 Add `ensure_entry_with_backfill(character_id)` helper in `talker_ws_query_handlers.script` (or delegate to memory_store_v2) that creates a memory entry if one doesn't exist and backfills from `global_event_buffer`
- [x] 3.2 Wire squad discovery: iterate squad members in the `query.character_info` handler, call `ensure_entry_with_backfill` for each

## 4. Lua Resource Handler (`talker_ws_query_handlers.script`)

- [x] 4.1 Register `query.character_info` in `resource_registry` — accept `params.id`, resolve character via `game_adapter.get_character_by_id(id)`
- [x] 4.2 Call `get_squad_members(char_obj)` to resolve squad members
- [x] 4.3 Call squad discovery side-effect (task 3.2) for each squad member
- [x] 4.4 Call `serialize_character_info(char, squad_members, memory_store)` to build the response
- [x] 4.5 Return serialized result; raise error if character not found

## 5. Python Tool Schema (`dialogue/conversation.py`)

- [x] 5.1 Add `GET_CHARACTER_INFO_TOOL` dict with `character_id` required parameter and description
- [x] 5.2 Add `get_character_info` to `TOOLS` list (now 3 tools total)
- [x] 5.3 Update system prompt in `_build_system_prompt()` to describe `get_character_info` tool — what it returns, when to use it

## 6. Python Tool Handler (`dialogue/conversation.py`)

- [x] 6.1 Add `_handle_get_character_info(character_id)` method — send `state.query.batch` with `query.character_info` sub-query
- [x] 6.2 Register `"get_character_info"` → `_handle_get_character_info` in `_tool_handlers` dict
- [x] 6.3 Add `_format_tool_result` handling for `get_character_info` — format character + squad members as readable text (name, faction, gender, traits summary, squad member list)
- [x] 6.4 Handle query failure — return `{"error": "..."}` and log warning

## 7. Python Tests

- [x] 7.1 Unit test `_handle_get_character_info` — mock state_client, verify batch query structure and response handling
- [x] 7.2 Unit test `_handle_get_character_info` with empty squad — verify `squad_members: []` passthrough
- [x] 7.3 Unit test `_handle_get_character_info` failure — verify error dict returned
- [x] 7.4 Unit test `_format_tool_result("get_character_info", ...)` — verify readable formatting with gender and background
- [x] 7.5 Unit test tool loop integration — mock `complete_with_tools` to call `get_character_info`, verify handler dispatch and message history
- [x] 7.6 Verify `GET_CHARACTER_INFO_TOOL` schema has correct structure (name, parameters, required fields)
- [x] 7.7 Verify `TOOLS` list contains all 3 tool definitions

## 8. Lua Tests

- [x] 8.1 Unit test `serialize_character_with_gender` in test_serializer.lua
- [x] 8.2 Unit test `serialize_character_info` with mocked memory_store — character with background, without background, with squad, without squad
- [x] 8.3 Integration test for `query.character_info` resource handler (if test harness supports resource registry testing)
