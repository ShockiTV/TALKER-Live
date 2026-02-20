## Why

`talker_trigger_map_transition.script` persists `previous_map` and `level_visit_count` as module-level locals via `save_state`/`load_state`. This is the "mini-store in a .script file" anti-pattern — domain state scattered in trigger scripts instead of proper repos. Additionally, the current `level_visit_count` is just a flat counter table with no context about when visits happened or who accompanied the player.

A proper `levels` domain repo would consolidate this state, enrich visit tracking with timestamps, companion lists, and origin levels, and provide a foundation for richer map-aware prompts (e.g. "first time here", "you last visited with X").

## What Changes

- Create `bin/lua/domain/repo/levels.lua` — new domain repo following the envelope save pattern:
  ```lua
  {
      levels_version = 1,
      levels = {
          from_level = "l01_escape",       -- replaces previous_map, transition detection
          visits = {
              ["l01_escape"] = {
                  count = 5,               -- authoritative, never decremented
                  log = {                   -- prunable visit history
                      { game_time_ms = 1234567, from_level = "l02_garbage", companions = {"uid_001"} },
                  }
              },
          }
      }
  }
  ```
- Pruning config read from MCM via `interface.config` (0 = no pruning, N = keep last N log entries per level), pruning happens on `get_save_data()`
- Standard repo API: `record_visit()`, `get_visit_count()`, `get_log()`, `get_from_level()`, `get_save_data()`, `load_save_data()`
- Refactor `talker_trigger_map_transition.script` to use the new repo instead of local state
- Wire `levels` store into `talker_game_persistence.script` save/load hub
- Migrate existing `level_visit_count` and `previous_map` save data to new format on load

## Capabilities

### New Capabilities
- `levels-store`: Domain repo for level visit history with versioned persistence, pruning, and rich visit entries

### Modified Capabilities
- `talker-persistence`: Save/load for map transition state moves from trigger script to `levels` repo

## Impact

- `bin/lua/domain/repo/levels.lua` — new file
- `gamedata/scripts/talker_trigger_map_transition.script` — remove local state + save/load, consume repo
- `gamedata/scripts/talker_game_persistence.script` — wire new repo into save/load hub
- Backward-compatible migration of existing save data (flat `level_visit_count` + `previous_map` → new format)
- `talker_mcm.script` / MCM config — new setting for max visit entries per level
- `bin/lua/interface/config.lua` — new getter for the pruning setting
