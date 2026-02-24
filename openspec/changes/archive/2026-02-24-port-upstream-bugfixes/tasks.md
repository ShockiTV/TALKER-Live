## 1. Anomaly Data Table

- [x] 1.1 Create `bin/lua/domain/data/anomaly_sections.lua` with Set of ~75 anomaly section names and section→display-name mapping extracted from `talker_anomalies.xml`
- [x] 1.2 Implement `is_anomaly(section)` predicate (returns `true`/`false`, nil-safe)
- [x] 1.3 Implement `describe(section)` lookup (returns display name or `nil`)
- [x] 1.4 Expose `is_anomaly_section()` and `describe_anomaly_section()` through engine facade (`interface/engine.lua` → `talker_game_queries.script`)
- [x] 1.5 Write unit tests for `anomaly_sections.lua` (`tests/domain/data/test_anomaly_sections.lua`)

## 2. Injury Trigger Guards

- [x] 2.1 Add nil guard (`if not who then return end`) at top of `actor_on_hit_callback` in `talker_trigger_injury.script`
- [x] 2.2 Add self-damage guard (`if who == db.actor then return end`)
- [x] 2.3 Add anomaly guard using `queries.is_anomaly_section(who:section())`
- [x] 2.4 Guard `mcm.get("injury_threshold")` with `tonumber()` and fallback default `0.4`

## 3. Task Trigger Safe Entity Access

- [x] 3.1 Capture `story_id` via `server_entity:section_name()` in task trigger
- [x] 3.2 Safe-access `character_name()` with type check, fallback to `"Unknown"`
- [x] 3.3 Safe-access `rank()` with type check, fallback to `0`
- [x] 3.4 Safe-access `community()` with type check, fallback to `"stalker"`
- [x] 3.5 Guard `ranks.get_se_obj_rank_name()` call with type check
- [x] 3.6 Include `story_id` in the `task_giver_character` table construction

## 4. Serializer story_id Support

- [x] 4.1 Add `story_id = char.story_id` to `serialize_character()` in `infra/zmq/serializer.lua`
- [x] 4.2 Update serializer unit tests to verify `story_id` is included in wire format

## 5. Dialogue Cleaner Rejections

- [x] 5.1 Expand rejection list in `cleaner.py` from 4 to ~20+ entries, grouped by category (apology, inability, policy, identity, content block, deflection)
- [x] 5.2 Add unit tests for new rejection patterns
- [x] 5.3 Add unit test for false-positive safety (legitimate dialogue containing partial matches passes through)

## 6. Callout Dedup Typed Events

- [x] 6.1 Replace `event.description` matching with `event.type == EventType.CALLOUT` and `event.context.target.name` check in `talker_trigger_callout.script`
- [x] 6.2 Add nil-safe traversal for `event.context.target.name`
- [x] 6.3 Update callout event creation flags from `{}` to `{ is_callout = true, target_name = enemy.name }`

## 7. Anomaly Trigger Migration

- [x] 7.1 Replace `queries.load_xml(section)` in `actor_on_feeling_anomaly` with `queries.describe_anomaly_section(section)`
- [x] 7.2 Replace `queries.load_xml(section)` in `actor_on_hit_callback` with `queries.describe_anomaly_section(section)`
- [x] 7.3 Verify zero remaining `load_xml` calls in `talker_trigger_anomalies.script`
