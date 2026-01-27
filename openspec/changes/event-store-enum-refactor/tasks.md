# Tasks

## Phase 1: Core Infrastructure

- [x] Create `bin/lua/domain/model/event_types.lua` with EventType enum
- [x] Add `Event.create()` constructor for typed events in `event.lua`
- [x] Add `Event.get_involved_characters()` helper in `event.lua`
- [x] Add `TEMPLATES` table and `Event.describe()` function in `event.lua`
- [x] Add `talker_event()` to `interface/trigger.lua`
- [x] Add `talker_event` listener in `gamedata/scripts/talker_listener_game_event.script`

## Phase 2: Migrate Triggers (simplest to most complex)

- [x] Migrate `talker_trigger_weapon_jam.script` to typed events
- [x] Migrate `talker_trigger_reload.script` to typed events
- [x] Migrate `talker_trigger_injury.script` to typed events
- [x] Migrate `talker_trigger_anomalies.script` to typed events
- [x] Migrate `talker_trigger_sleep.script` to typed events
- [x] Migrate `talker_trigger_emission.script` to typed events
- [x] Migrate `talker_trigger_map_transition.script` to typed events
- [x] Migrate `talker_trigger_artifact.script` to typed events (4 actions)
- [x] Migrate `talker_trigger_task.script` to typed events
- [x] Migrate `talker_trigger_callout.script` to typed events
- [x] Migrate `talker_trigger_taunt.script` to typed events
- [x] Migrate `talker_trigger_death.script` to typed events
- [x] Migrate `talker_trigger_idle_conversation.script` to typed events

## Phase 3: Consumer Updates

- [x] Update `prompt_builder.lua` to use `Event.describe()` instead of raw description
- [x] Update `transformations.lua` to check `event.type` instead of flags (N/A - no flag checks found)
- [x] Update `game_adapter.lua` `create_dialogue_event()` to use typed events

## Phase 4: Cleanup

- [x] Remove deprecated flags from all triggers (`is_death`, `is_artifact`, etc.)
  - Migrated: death, artifact, anomaly, reload, weapon_jam, callout, taunt triggers
  - Legacy flags kept in `Event.is_junk_event()` for backward compatibility with old saves
- [x] Migrate remaining legacy usages (player_speaks, player_whispers listeners)
- [x] Update tests to use typed events
  - All tests now use `Event.create()` with `EventType` enum
  - Legacy `LEGACY_TYPE` removed from tests
- [x] Remove old `talker_game_event` interface from `trigger.lua`
- [x] Remove old `Event.create_event()` constructor
- [x] Remove `interface.register_game_event()` and related legacy functions
- [x] Remove `game_adapter.create_game_event()` 
- [x] Delete `talker_listener_game_event_near_player.script`

## Completion Status

**REFACTOR COMPLETE** - All triggers migrated to typed events.

All legacy interfaces removed:
- `Event.create_event()` - removed, use `Event.create()` instead
- `Event.LEGACY_TYPE` - removed, use `EventType` enum instead
- `interface.register_game_event()` - removed, use `interface.register_typed_event()` instead
- `interface.register_game_event_near_player()` - removed, use `interface.register_typed_event_near_player()` instead
- `interface.register_silent_event_near_player()` - removed, use flags `{ is_silent = true }`
- `interface.register_silent_event()` - removed
- `interface.register_character_instructions()` - removed
- `game_adapter.create_game_event()` - removed
- `trigger.talker_game_event()` - removed, use `trigger.talker_event()` instead
- `trigger.talker_game_event_near_player()` - removed, use `trigger.talker_event_near_player()` instead
- `trigger.talker_character_instructions()` - removed
- `trigger.talker_silent_event_near_player()` - removed
- `trigger.talker_silent_event()` - removed
- `talker_listener_game_event_near_player.script` - deleted

Note: `Event.is_junk_event()` still supports legacy flag-based detection for backward compatibility with old save data.
