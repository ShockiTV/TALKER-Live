# Tasks

## Phase 1: Core Infrastructure

- [ ] Create `bin/lua/domain/model/event_types.lua` with EventType enum
- [ ] Add `Event.create()` constructor for typed events in `event.lua`
- [ ] Add `Event.get_involved_characters()` helper in `event.lua`
- [ ] Add `TEMPLATES` table and `Event.describe()` function in `event.lua`
- [ ] Add `talker_event()` to `interface/trigger.lua`
- [ ] Add `talker_event` listener in `gamedata/scripts/talker_listener_game_event.script`

## Phase 2: Migrate Triggers (simplest to most complex)

- [ ] Migrate `talker_trigger_weapon_jam.script` to typed events
- [ ] Migrate `talker_trigger_reload.script` to typed events
- [ ] Migrate `talker_trigger_injury.script` to typed events
- [ ] Migrate `talker_trigger_anomalies.script` to typed events
- [ ] Migrate `talker_trigger_sleep.script` to typed events
- [ ] Migrate `talker_trigger_emission.script` to typed events
- [ ] Migrate `talker_trigger_map_transition.script` to typed events
- [ ] Migrate `talker_trigger_artifact.script` to typed events (4 actions)
- [ ] Migrate `talker_trigger_task.script` to typed events
- [ ] Migrate `talker_trigger_callout.script` to typed events
- [ ] Migrate `talker_trigger_taunt.script` to typed events
- [ ] Migrate `talker_trigger_death.script` to typed events
- [ ] Migrate `talker_trigger_idle_conversation.script` to typed events

## Phase 3: Consumer Updates

- [ ] Update `prompt_builder.lua` to use `Event.describe()` instead of raw description
- [ ] Update `transformations.lua` to check `event.type` instead of flags
- [ ] Update `game_adapter.lua` `create_dialogue_event()` to use typed events

## Phase 4: Cleanup

- [ ] Remove deprecated flags from all triggers (`is_death`, `is_artifact`, etc.)
- [ ] Remove old `Event.create_event()` constructor (after all triggers migrated)
- [ ] Remove old `talker_game_event` interface (after all triggers migrated)
- [ ] Update tests to use typed events
