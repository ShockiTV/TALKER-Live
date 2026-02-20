## Context

Map transition state is currently split: `previous_map` and `level_visit_count` live as module-level locals in `talker_trigger_map_transition.script` with inline `save_state`/`load_state`. This mixes domain data with trigger logic. Other domain state (memories, events, personalities, backstories) already lives in `bin/lua/domain/repo/` with a consistent versioned persistence pattern and centralized save/load in `talker_game_persistence.script`.

The trigger script currently saves a flat `level_visit_count` table (map → integer) and a `previous_map` string. The `previous_map` is infrastructure (transition detection across VM resets), while visit counts are domain data useful for prompts.

## Goals / Non-Goals

**Goals:**
- Create `bin/lua/domain/repo/levels.lua` with a richer data model than the current flat counter
- Follow the existing envelope save pattern (`levels_version` + `levels` data key)
- Keep `from_level` (transition detection) inside the store since it belongs to the level domain
- Store visit log entries with `game_time_ms`, `from_level`, and `companions` per visit
- Separate authoritative `count` from prunable `log` per level
- Support configurable pruning via MCM (0 = no pruning, N = keep last N entries per level)
- Migrate existing save data (flat `level_visit_count` + `previous_map`) on load
- Wire into `talker_game_persistence.script` central save/load hub
- Remove save/load from the trigger script

**Non-Goals:**
- Exposing visit data to Python service via ZMQ queries (future work)
- Changing the map transition event itself or its context fields
- Modifying other stores to share a common base (each store stays independent)

## Decisions

### 1. Data structure: per-level objects with count + log

```lua
{
    levels_version = 1,
    levels = {
        from_level = "l01_escape",
        visits = {
            ["l01_escape"] = {
                count = 5,
                log = {
                    { game_time_ms = 1234567, from_level = "l02_garbage", companions = {"uid_001"} },
                }
            },
        }
    }
}
```

**Why over separate `visit_count` + `visits` tables**: Co-locating `count` and `log` per level avoids parallel tables that must stay in sync. `count` is authoritative (never decremented, survives pruning). `log` is the prunable detail.

**Alternative considered**: Flat counter only (current approach) — rejected because it loses when/who context that enriches prompts.

### 2. `from_level` inside `levels` namespace, not at envelope root

`from_level` is level-domain state (transition detection), not save metadata. It sits inside the `levels` data object rather than alongside `levels_version`.

**Alternative considered**: Keep `previous_map` in the trigger script — rejected because it's persisted state that belongs with other level data.

### 3. Pruning on `get_save_data()`, config from MCM

Pruning happens during save, not at record time. The store always keeps all entries in memory — only trims when serializing. This keeps runtime queries simple (full history available) while bounding save file size.

MCM setting with default 0 (no pruning). Exposed via `interface.config` getter. The store reads the config at save time.

**Alternative considered**: Hardcoded constant in the store — rejected per user preference for MCM configurability.

### 4. Companions stored as game object IDs

Visit log entries store companion IDs (game engine `se_obj.id` integers), not names. IDs are stable across sessions. Name resolution happens at prompt build time if/when this data is sent to Python.

### 5. Migration from legacy format

On `load_save_data()`, detect legacy format (flat table with integer values, no `levels_version`). Migrate:
- Each `level_visit_count[level] = N` → `visits[level] = { count = N, log = {} }`
- `previous_map` needs to be passed separately since it's stored under a different key in the old save. The persistence hub will handle this during the transition.

Version 1 is the first versioned format. Legacy unversioned saves are treated as version 0.

### 6. Trigger script keeps `previous_map` local as read-through

The trigger script still needs `previous_map` for `has_map_changed()` in `on_loading_screen_dismissed`. It reads from the repo on load rather than managing its own persistence. The repo is the source of truth.

## Risks / Trade-offs

- **Save file growth** → Mitigated by pruning config. Default 0 (no pruning) is fine for most players; heavy players can set a cap.
- **Migration complexity for `previous_map`** → The old save stores `previous_map` at `m_data.previous_map` (trigger script's save_state), while the new store expects it inside the repo's data. The persistence hub migration code must read from the old location during the transition. Risk: one-time migration path, tested and then dead code.
- **Companion ID availability at record time** → `game.get_companions()` returns character objects during the transition event handler. Need to extract IDs there. If companions are somehow unavailable, store empty list.
