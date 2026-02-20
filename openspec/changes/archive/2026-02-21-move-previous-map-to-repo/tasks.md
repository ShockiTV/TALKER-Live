## 1. Levels Store

- [x] 1.1 Create `bin/lua/domain/repo/levels.lua` with data structure, `record_visit()`, `get_visit_count()`, `get_log()`, `get_from_level()`, `set_from_level()`, `clear()`
- [x] 1.2 Implement `get_save_data()` with envelope pattern (`levels_version = 1`, `levels` data key) and pruning logic
- [x] 1.3 Implement `load_save_data()` with version check and legacy migration (flat `level_visit_count` + `from_level` → new format)

## 2. MCM & Config

- [x] 2.1 Add `max_log_entries_per_level` setting to `talker_mcm.script` (default 0 = no pruning)
- [x] 2.2 Add `max_log_entries_per_level()` getter to `bin/lua/interface/config.lua`

## 3. Persistence Hub Integration

- [x] 3.1 Wire `levels` store into `talker_game_persistence.script` save_state/load_state
- [x] 3.2 Add legacy migration bridge: if `saved_data.levels` is nil, check for old `level_visit_count`/`previous_map` keys and pass to `load_save_data()`

## 4. Trigger Script Refactor

- [x] 4.1 Refactor `talker_trigger_map_transition.script` to require `levels` repo and call `record_visit()` in `on_map_change_event()`
- [x] 4.2 Replace local `previous_map` with `levels.get_from_level()` in `has_map_changed()` and `levels.set_from_level()` in `save_state`
- [x] 4.3 Remove local `level_visit_count`, `previous_map`, and the script's own `save_state`/`load_state` callbacks
- [x] 4.4 Remove dead `on_level_changing` callback registration

## 5. Tests

- [x] 5.1 Create `tests/repo/test_levels.lua` — record, query count, query log, from_level, clear
- [x] 5.2 Test versioned save/load round-trip
- [x] 5.3 Test legacy migration (flat visit count + from_level → new format)
- [x] 5.4 Test pruning on save (0 = no pruning, N = keep last N)
