## 1. Create timers repo module

- [x] 1.1 Create `bin/lua/domain/repo/timers.lua` with internal `data` table (`game_time_accumulator = 0`, `idle_last_check_time = 0`), public getters `get_game_time_accumulator()` and `get_idle_last_check_time()`, setter `set_idle_last_check_time(v)`, and `clear()`
- [x] 1.2 Add `get_save_data(current_game_time_ms)` returning `{ timers_version = 1, timers = { game_time_accumulator = current_game_time_ms, idle_last_check_time = data.idle_last_check_time } }`
- [x] 1.3 Add `load_save_data(saved_data)` handling: nil → clear, versioned v1 → restore, unknown version → warn + clear, no version → legacy migration mapping `game_time_since_last_load` → `game_time_accumulator` and `talker_idle_last_check_time_ms` → `idle_last_check_time`

## 2. Wire into persistence

- [x] 2.1 In `talker_game_persistence.script`: require `timers` store, add `saved_data.timers = timers_store.get_save_data(talker_game_queries.get_game_time_ms())` to `save_state`
- [x] 2.2 In `talker_game_persistence.script`: add timers load block to `load_state` with legacy bridge — if `saved_data.timers` exists load it, else if old top-level keys exist pass them to `load_save_data`, else call with nil

## 3. Refactor game scripts

- [x] 3.1 In `talker_game_queries.script`: require timers store, change `get_game_time_ms()` to `return time_global() + timers.get_game_time_accumulator()`, remove `game_time_since_last_load` local, remove `save_game_time`/`load_game_time` functions, remove their `RegisterScriptCallback` lines from `on_game_start`
- [x] 3.2 In `talker_trigger_idle_conversation.script`: require timers store, replace local `last_check_time_ms` reads/writes with `timers.get_idle_last_check_time()` / `timers.set_idle_last_check_time(v)`, remove `save_state`/`load_state` functions, remove their `RegisterScriptCallback` lines from `on_game_start`, keep `last_idle_conversation_time_ms` reset in `on_game_start` (volatile, not persisted)

## 4. Tests

- [x] 4.1 Create `tests/repo/test_timers.lua` covering: fresh state returns zeros, set/get idle check time, `get_save_data` envelope structure, `load_save_data` with versioned data, `load_save_data` with nil, `load_save_data` with unknown version, legacy migration with both keys, legacy migration with partial keys, `clear()` resets all values
