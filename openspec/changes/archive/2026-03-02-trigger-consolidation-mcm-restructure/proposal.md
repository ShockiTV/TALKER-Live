## Why

The 13 trigger scripts each implement their own ad-hoc gating logic: MCM reads at module load time (stale values), three-state `radio_h` modes (On/Off/Silent) that produce `is_silent` flags for Python, per-trigger cooldown wiring, and inconsistent chance rolls. The result:

- **Stale MCM reads**: All triggers read MCM at `require()` time (`local mode = mcm.get(...)`) and never re-read. Mid-game MCM changes have no effect until save/reload.
- **Flag soup**: `is_silent`, `is_idle`, `is_callout`, `important_death` flags are passed through the event pipeline. Python ignores most of them. `important_death` is vestigial. `is_silent` duplicates what `chance=0` would express.
- **Split gating**: Both Lua triggers AND `store_and_publish` participate in the store/speak decision. The design doc says Lua should decide everything — Python only generates dialogue for events that reach it.
- **No per-trigger chance**: There's a global `base_dialogue_chance` (float 0.0–1.0 track slider) but no per-trigger chance settings. All triggers that aren't "always speak" use the same global probability.
- **MCM structure is flat**: All settings are in a single flat `gr` array. The design doc specifies nested `talker/triggers/<type>/` subsections with uniform `enable` + `cooldown` + `chance` patterns.

## What Changes

### Trigger Layer
- Split `store_and_publish()` into `store_event()` (memory only) and `publish_event()` (memory + WS)
- Add `domain/service/chance.lua` — shared `chance.check(mcm_key)` utility
- Update all 13 trigger scripts to use the new consolidated flow: enable check → anti-spam/cooldown → `is_important` OR `chance.check()` → branch to `store_event` or `publish_event`
- All MCM reads become dynamic (read via `config.get()` at call time, not module load)
- Remove `flags` parameter from trigger API — no more `is_silent` in event data
- Remove old backward-compat `talker_event` and `talker_event_near_player` from trigger.lua

### MCM Layer
- Replace all `radio_h` On/Off/Silent controls with `check` (enable) + `input` (chance 0–100)
- Add per-trigger `chance` integer inputs (0–100) with appropriate defaults
- Restructure triggers section into nested subsections (`sh = true`) per trigger type
- Remove global `base_dialogue_chance` — replaced by per-trigger `chance` settings
- Add `config_defaults.lua` entries for all new MCM keys

### Python Side
- Remove any remaining `flags` reads from event handlers (already mostly gone)
- `flags` field ignored on wire schema (backward compat — not removed from schema)

## Capabilities

### New Capabilities
- `trigger-engine`: Consolidated trigger flow with `store_event`/`publish_event` split, shared chance utility, and dynamic MCM reads
- `mcm-trigger-settings`: Per-trigger MCM subsections with uniform `enable` + `cooldown` + `chance` pattern, replacing `radio_h` On/Off/Silent

### Modified Capabilities
- `cooldown-manager`: Simplify to work with new 2-state `enable`/`chance` system instead of 3-state mode (On/Off/Silent). The `mode` parameter in `check()` becomes a simple boolean enable check.
- `talker-mcm`: Restructure triggers section from flat list to nested subsections; remove `base_dialogue_chance`; add per-trigger chance inputs

## Impact

- **13 trigger scripts** (`gamedata/scripts/talker_trigger_*.script`): All rewritten to use new flow — dynamic MCM, chance utility, store/publish split
- **`interface/trigger.lua`**: `store_and_publish` → `store_event` + `publish_event`; remove old compat functions
- **`interface/config.lua`**: Add getters for new per-trigger MCM keys; remove `BASE_DIALOGUE_CHANCE`
- **`interface/config_defaults.lua`**: Add defaults for all new trigger MCM keys
- **`domain/service/cooldown.lua`**: Adapt `check()` to new 2-state system
- **`domain/service/chance.lua`**: New module
- **`talker_mcm.script`**: Restructured triggers section
- **MCM localization** (`gamedata/configs/text/`): New string IDs for per-trigger settings
- **Python event handler**: Minor cleanup — stop reading `flags` dict
- **No wire protocol changes**: Events still flow as `game.event` topic; `flags` field preserved but ignored
- **Breaking MCM change**: Users' existing trigger mode settings (radio_h values) won't migrate — they'll get defaults. This is acceptable for a mod update.
