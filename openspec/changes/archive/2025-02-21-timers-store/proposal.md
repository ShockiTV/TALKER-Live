## Why

Two timer values — the game time accumulator (`game_time_since_last_load` in `talker_game_queries.script`) and the idle check timer (`last_check_time_ms` in `talker_trigger_idle_conversation.script`) — persist via inline `save_state`/`load_state` callbacks, bypassing the centralized `domain/repo/` persistence architecture. Consolidating both into a single `timers.lua` repo module eliminates the last inline persistence and follows the established envelope pattern used by all other stores.

## What Changes

- Create `bin/lua/domain/repo/timers.lua` — a module-level repo store holding two persisted timer values (`game_time_accumulator`, `idle_last_check_time`) with the standard envelope save/load API
- Wire `timers.lua` into `talker_game_persistence.script` under `saved_data.timers` with a `timers_version` envelope, including a legacy migration bridge for old top-level keys
- Refactor `talker_game_queries.script` to read `game_time_accumulator` from the timers store (read-only dependency) and remove its inline `save_state`/`load_state` callbacks
- Refactor `talker_trigger_idle_conversation.script` to read/write `idle_last_check_time` through the timers store and remove its inline `save_state`/`load_state` callbacks
- `get_save_data(current_game_time_ms)` accepts the current computed game time from the persistence script, so the store never depends on `time_global()`

## Capabilities

### New Capabilities
- `timers-store`: Domain repo module for persisting timer values (game time accumulator, idle check timer) across saves with versioned envelope pattern

### Modified Capabilities
- `talker-persistence`: Adds timers store save/load alongside existing stores, with legacy migration bridge for old inline keys

## Impact

- `bin/lua/domain/repo/timers.lua` — new file
- `gamedata/scripts/talker_game_persistence.script` — add timers store require, save/load, legacy bridge
- `gamedata/scripts/talker_game_queries.script` — remove inline save/load callbacks, require timers store for accumulator read
- `gamedata/scripts/talker_trigger_idle_conversation.script` — remove inline save/load callbacks, require timers store for idle timer read/write
- `tests/repo/test_timers.lua` — new test file
- Low–medium risk: game time accumulator is high-coupling (all timestamps flow through `get_game_time_ms()`), but the computation logic stays in queries — only persistence moves
