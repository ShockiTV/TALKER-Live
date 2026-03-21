## Context

There are 13 trigger scripts in `gamedata/scripts/talker_trigger_*.script`. Each implements its own gating: MCM mode read, cooldown construction, silence flag computation, and call to `trigger.store_and_publish()`. The current MCM uses `radio_h` with On/Off/Silent states, and a global `base_dialogue_chance` float track slider. The design doc (`docs/Tools_Based_Memory.md`, §"Trigger Architecture: Consolidated Event Intent") specifies collapsing the three-state radio into `enable` (checkbox) + `chance` (integer 0–100), eliminating all event flags, and splitting the trigger API into `store_event` / `publish_event`.

Current trigger flow: trigger fires → MCM mode check (stale) → cooldown `check(slot, time, mode)` → returns nil/true/false → `store_and_publish(type, context, witnesses, flags)` → always stores + always publishes.

Target flow: trigger fires → `config.get("triggers/<type>/enable")` (dynamic) → cooldown check → `is_important OR chance.check("triggers/<type>/chance")` → fail → `trigger.store_event(...)` (no WS) / pass → `trigger.publish_event(...)` (WS + memory).

## Goals / Non-Goals

### Goals
- Split `trigger.store_and_publish()` into `trigger.store_event()` and `trigger.publish_event()`
- Create `domain/service/chance.lua` shared chance utility
- Make all MCM reads dynamic (call `config.get()` at trigger time, not module load)
- Replace `radio_h` On/Off/Silent with `check` (enable) + `input` (chance 0–100) per trigger
- Add nested MCM subsections (`talker/triggers/<type>/`)
- Remove `flags` parameter from trigger API
- Remove `base_dialogue_chance` global setting
- Remove old backward-compat `talker_event` and `talker_event_near_player`
- Adapt `CooldownManager.check()` to new 2-state enable system
- Update all 13 trigger scripts to use consolidated flow

### Non-Goals
- New trigger types (no new event types added)
- Python-side event filtering changes (already clean — just stop reading `flags`)
- Wire protocol changes (events still use `game.event` topic)
- MCM save migration (users get fresh defaults — acceptable for mod update)
- Memory system changes (compaction, tiers, etc.)
- Changing the Event model or EventType enum

## Decisions

### D1: store_event vs publish_event split

**Decision**: `trigger.store_event(event_type, context, witnesses)` stores to memory only (fan-out to witnesses, no WS publish). `trigger.publish_event(event_type, context, witnesses)` stores to memory AND publishes via WS. Both create the Event object identically — the only difference is whether `publisher.send_game_event()` is called.

**Rationale**: Clean separation of "remember this happened" vs "react to this". The old `store_and_publish` always did both. With the chance system, `chance=0` events should still be remembered by NPCs but never trigger dialogue. Making `publish_event` call `store_event` internally avoids duplication.

### D2: CooldownManager simplification

**Decision**: Keep `CooldownManager.check(slot, current_time, mode)` signature but the `mode` parameter changes semantics. The caller now passes a simple boolean-like value: `0` for enabled (check cooldown), any non-zero for disabled (abort). Mode `2` (Silent) is **removed** — it's replaced by `chance=0`.

Actually, re-evaluating: the cleaner approach is to keep `CooldownManager` as-is (its `check()` already works correctly for mode 0=On, 1=Off) and simply never pass mode=2 anymore. Triggers that are `enable=true, chance=0` pass mode=0 to the cooldown manager (events are created but chance roll always fails — store-only). Triggers with `enable=false` skip entirely before reaching cooldown.

**Revised Decision**: `CooldownManager` is **unchanged**. Triggers just stop using mode=2. The flow is: `enable=false` → early return (no event). `enable=true` → cooldown check with mode=0 → if cooldown says "silent" (true), treat as store-only. If cooldown says "speak" (false), check `is_important OR chance.check()` → pass → publish, fail → store. This preserves the anti-spam behavior where cooldown-active events are stored silently.

### D3: Chance utility design

**Decision**: `domain/service/chance.lua` exports `M.check(mcm_key) → boolean`. Reads `config.get(mcm_key)` at call time (dynamic). Returns `true` if `math.random(1, 100) <= pct`, false otherwise. Special cases: `pct >= 100` → always true, `pct <= 0` → always false.

**Rationale**: One-liner utility. Every trigger calls `chance.check("triggers/<type>/chance")`. No need for a class — pure function is sufficient. Using `config.get()` (which reads through engine facade) ensures MCM changes take effect immediately.

### D4: MCM structure — nested `gr` hierarchy

**Decision**: Use nested `gr` groups to create a two-level navigation tree under `talker/`. The root `talker` group has NO `sh=true` (enabling navigation), containing two sub-groups: `general` (with `sh=true` — shows all non-trigger settings as an options page) and `triggers` (no `sh` — navigation to per-trigger pages). Each trigger type is a `sh=true` leaf group showing its own settings.

```
talker/                        (root, NO sh — enables navigation tree)
  general/                     (sh=true — options page)
    gpt_version, ai_model_method, ..., debug_logging, service_url, ...
  triggers/                    (NO sh — navigation to trigger sub-pages)
    death/                     (sh=true — options page)
      enable_player  (check)
      cooldown_player (input, seconds)
      chance_player  (input, 0-100)
      enable_npc     (check)
      cooldown_npc   (input, seconds)
      chance_npc     (input, 0-100)
    injury/                    (sh=true — options page)
      enable         (check)
      cooldown       (input, seconds)
      chance         (input, 0-100)
    ...
```

The `get()` function routes keys: `triggers/*` → `talker/triggers/*`, all others → `talker/general/*`. Callers are unaffected.

**Rationale**: The MCM API in Anomaly builds a navigation tree from nested `gr` arrays without `sh`. Groups with `sh=true` become leaf pages showing their options directly. This gives users a clean two-level navigation (General / Triggers → per-type) instead of a single massive scrollable page with ~60+ settings.

### D5: Dynamic MCM reads

**Decision**: Remove all `local mode = mcm.get(...)` at module scope in trigger scripts. Replace with `config.get("triggers/<type>/enable")` calls inside the callback functions. The `config.get()` function reads through the engine facade, which calls `talker_mcm.get()` at runtime.

**Rationale**: Current triggers read MCM once at `require()` time — values are stale for the entire game session. Dynamic reads let players change trigger settings in MCM and see immediate effect.

### D6: Backward compatibility — flags and wire protocol

**Decision**: The `flags` dict is removed from `store_event/publish_event` signatures. Events still carry a `flags` field in the Event object (empty `{}`), so the wire format doesn't break. Python's event handler already ignores flags.

**Rationale**: Clean break on the Lua side. Wire protocol backward compat costs nothing (empty dict). New trigger scripts never populate flags.

### D7: is_important stays as local logic

**Decision**: `is_important` remains a local variable inside each trigger, computed from character data (player, companion, unique NPC, high rank). It short-circuits the chance roll: `if is_important then publish_event(...) else chance.check(...) end`. It is never sent on the wire or stored in the event.

**Rationale**: The design doc explicitly says `is_important` is a local variable that overrides the chance roll for significant events. Moving it to a shared `importance.lua` service already exists (`domain/service/importance.lua` has `is_important_person(flags)`) — triggers should use this.

### D8: Triggers that have sub-types

**Decision**: Triggers with sub-actions (artifact: pickup/use/equip; death: player/npc; anomaly: proximity/damage) have separate MCM keys for each sub-type. Each sub-type gets its own `enable`, `cooldown`, `chance` triplet. This matches the design doc's MCM structure.

**Rationale**: Players want granular control. "I want artifact pickups to always trigger dialogue but artifact equips to be silent" is a valid preference.

## Risks / Trade-offs

### R1: Breaking MCM settings for existing users
**Risk**: Existing users' `radio_h` values (0/1/2) will not map to the new `check` + `input` structure. Settings reset to defaults.
**Mitigation**: Acceptable for a mod update. Defaults are sensible. Document in CHANGELOG.

### R2: Large changeset across 13 files
**Risk**: Touching all 13 trigger scripts simultaneously is high-risk for regressions.
**Mitigation**: Each trigger follows the exact same pattern. Test the pattern on 2-3 triggers first, then apply mechanically to the rest. Lua tests cover cooldown and chance modules.

### R3: MCM localization strings
**Risk**: New string IDs for all per-trigger settings require localization entries.
**Mitigation**: Start with English only. The MCM generates reasonable default labels from IDs.

### R4: CooldownManager behavior shift
**Risk**: Never passing mode=2 anymore changes when events are created vs skipped.
**Mitigation**: With `chance=0`, the cooldown still runs with mode=0. An on-cooldown event returns `true` (silent → store only). An off-cooldown event fails the chance roll → also store only. Same end result as old Silent mode, just via a different code path.
