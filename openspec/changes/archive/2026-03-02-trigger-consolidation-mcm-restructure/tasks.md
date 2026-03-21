## 1. Trigger API (`interface/trigger.lua`)

- [x] 1.1 Add `store_event(event_type, context, witnesses)` — create Event, store in speaker memory, fan out to witnesses, no WS publish
- [x] 1.2 Add `publish_event(event_type, context, witnesses)` — call `store_event` internally, then call `publisher.send_game_event()` with candidates, world, traits
- [x] 1.3 Remove `store_and_publish()` function
- [x] 1.4 Remove `talker_event()` backward-compat function
- [x] 1.5 Remove `talker_event_near_player()` backward-compat function

## 2. Chance Utility (`domain/service/chance.lua`)

- [x] 2.1 Create `domain/service/chance.lua` with `M.check(mcm_key) → boolean`
- [x] 2.2 Read MCM value dynamically via `config.get(mcm_key)` — integer 0-100
- [x] 2.3 Handle edge cases: `pct >= 100 → true`, `pct <= 0 → false`, otherwise `math.random(1, 100) <= pct`
- [x] 2.4 Write unit tests for chance module (always true, always false, boundary values)

## 3. MCM Restructure (`talker_mcm.script`)

- [x] 3.1 Replace flat trigger settings with nested `sh = true` subsections per trigger type
- [x] 3.2 Replace all `radio_h` On/Off/Silent controls with `check` (enable boolean)
- [x] 3.3 Add `chance` integer inputs (0–100) per trigger sub-type with defaults from design doc
- [x] 3.4 Keep `cooldown` inputs per trigger sub-type (rename IDs to match nested path convention)
- [x] 3.5 Remove `base_dialogue_chance` track slider from MCM
- [x] 3.6 Add idle sub-mode settings: `enable_during_emission`, `cooldown_during_emission`, `chance_during_emission`, `enable_during_psy_storm`, `cooldown_during_psy_storm`, `chance_during_psy_storm`

## 4. Config Defaults (`interface/config_defaults.lua`)

- [x] 4.1 Add default values for all new `triggers/*` MCM keys (enable, cooldown, chance per type)
- [x] 4.2 Remove `base_dialogue_chance` default
- [x] 4.3 Add config getters in `interface/config.lua` for new trigger keys

## 5. Trigger Script Updates (13 scripts)

- [x] 5.1 Update `talker_trigger_death.script` — dynamic MCM reads, consolidated flow (enable → cooldown → importance/chance → store/publish)
- [x] 5.2 Update `talker_trigger_injury.script` — same pattern
- [x] 5.3 Update `talker_trigger_artifact.script` — 3 sub-types (pickup/use/equip), each with own enable/cooldown/chance
- [x] 5.4 Update `talker_trigger_anomalies.script` — 2 sub-types (proximity/damage)
- [x] 5.5 Update `talker_trigger_callout.script` — dynamic MCM, consolidated flow
- [x] 5.6 Update `talker_trigger_taunt.script` — dynamic MCM, consolidated flow
- [x] 5.7 Update `talker_trigger_emission.script` — enable + chance only (no cooldown)
- [x] 5.8 Update `talker_trigger_idle_conversation.script` — base + emission/psy_storm sub-modes
- [x] 5.9 Update `talker_trigger_map_transition.script` — enable + chance only (no cooldown)
- [x] 5.10 Update `talker_trigger_sleep.script` — enable + chance only
- [x] 5.11 Update `talker_trigger_reload.script` — dynamic MCM, consolidated flow
- [x] 5.12 Update `talker_trigger_task.script` — dynamic MCM, consolidated flow
- [x] 5.13 Update `talker_trigger_weapon_jam.script` — dynamic MCM, consolidated flow

## 6. Python Cleanup

- [x] 6.1 Remove any `flags` dict reads from `handlers/events.py` (verify already clean)
- [x] 6.2 Add code comment noting `flags` field is deprecated but preserved for wire compat

## 7. MCM Localization

- [x] 7.1 Add English string IDs for all new MCM keys in `gamedata/configs/text/` localization files

## 8. Tests

- [x] 8.1 Unit tests for `chance.check()` — always-pass, always-fail, boundary, dynamic MCM read
- [x] 8.2 Unit tests for `trigger.store_event()` — verify memory store, fan-out, no WS publish
- [x] 8.3 Unit tests for `trigger.publish_event()` — verify memory store, fan-out, AND WS publish
- [x] 8.4 Integration test: full trigger flow (enable → cooldown → chance → store/publish branching)
- [x] 8.5 Verify existing CooldownManager tests still pass unchanged
