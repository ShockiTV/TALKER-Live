## Why

The Lua codebase contains vestigial code from before the Phase 2 migration to Python-based AI processing. This includes broken references in `talker_game_load_check.script` that will cause runtime errors, unused HTTP infrastructure that is no longer needed since AI moved to Python, and dead imports/functions in domain and infra layers. Cleaning this up reduces maintenance burden and prevents confusion.

## What Changes

- **Remove broken module references** in `talker_game_load_check.script` that point to non-existent files (`infra.STALKER.unique_backstories`, `infra.STALKER.unique_personalities`)
- **Remove unused Item import** from `domain/model/event.lua` (imported but never used)
- **Remove dead functions** from `game_adapter.lua`: `get_player_weapon()` and `create_item()` (never called by production code)
- **Delete vestigial HTTP module** `infra/HTTP/HTTP.lua` and `infra/HTTP/pollnet.lua` (only used by tests, not production - AI calls moved to Python)
- **Clean up related test files** that test the dead HTTP code

## Capabilities

### New Capabilities
<!-- None - this is a cleanup change -->

### Modified Capabilities
<!-- None - no spec-level behavior changes -->

## Impact

- **`gamedata/scripts/talker_game_load_check.script`** - Removes 2 invalid module references
- **`bin/lua/domain/model/event.lua`** - Removes unused Item import
- **`bin/lua/domain/model/item.lua`** - May become fully vestigial (only used by dead code)
- **`bin/lua/infra/game_adapter.lua`** - Removes 2 unused functions (~15 lines)
- **`bin/lua/infra/HTTP/HTTP.lua`** - Delete entire file
- **`bin/lua/infra/HTTP/pollnet.lua`** - Delete entire file
- **`bin/lua/infra/HTTP/json.lua`** - Keep (still used by ZMQ bridge, recorder)
- **`tests/live/real_http_requests/`** - Delete test directory (tests dead code)
