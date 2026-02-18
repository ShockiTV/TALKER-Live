# Tasks: World State Migration Fix

## 1. Python: Important Characters Registry

- [x] 1.1 Create `texts/characters/important.py` with CHARACTERS dict containing all faction leaders, important, and notable characters (port from fork's `world_state.lua`)
- [x] 1.2 Each entry must include: story_id (or ids list), name, role, faction, optional area, optional description

## 2. Python: State Models for Scene Query

- [x] 2.1 Create `SceneContext` model in `state/models.py` with fields: loc, poi, time (dict), weather, emission, psy_storm, sheltering, campfire, brain_scorcher_disabled, miracle_machine_disabled
- [x] 2.2 Add `CharactersAliveResponse` model for characters.alive query response

## 3. Python: World Context Builder

- [x] 3.1 Create `prompts/world_context.py` module
- [x] 3.2 Implement `query_characters_alive(state_client, ids)` that sends characters.alive query and returns dict
- [x] 3.3 Implement `build_dead_leaders_context(alive_status)` that returns formatted text for dead faction leaders
- [x] 3.4 Implement `build_dead_important_context(alive_status, current_area, recent_events)` with notable filtering
- [x] 3.5 Implement `build_info_portions_context(scene_data)` for Brain Scorcher and Miracle Machine
- [x] 3.6 Implement `build_regional_context(current_area)` for Cordon truce
- [x] 3.7 Implement `build_world_context(scene_data, recent_events, state_client)` aggregator

## 4. Python: Remove world_context from Event Model

- [x] 4.1 Remove `world_context: str = ""` field from Event dataclass in `prompts/models.py`
- [x] 4.2 Update `Event.from_dict()` to ignore world_context in payload (backward compatibility)
- [x] 4.3 Update any tests that reference event.world_context

## 5. Lua: Characters Alive Query Handler

- [x] 5.1 Add `get_story_object(id)` helper in `talker_zmq_query_handlers.script` (port from fork's `world_state.lua`)
- [x] 5.2 Add `handle_characters_alive(payload)` handler that iterates IDs, checks alive status with fallback logic
- [x] 5.3 Register handler for `characters.alive` query type

## 6. Lua: Extend World Context Query

- [x] 6.1 Add `brain_scorcher_disabled` field to world.context response (check `has_alife_info("bar_deactivate_radar_done")`)
- [x] 6.2 Add `miracle_machine_disabled` field (check `has_alife_info("yan_kill_brain_done")`)
- [x] 6.3 Update response to return time as object `{Y, M, D, h, m, s, ms}` instead of formatted string

## 7. Lua: Remove world_context from Events

- [x] 7.1 Update `Event.create()` signature to remove world_context parameter
- [x] 7.2 Update `interface.lua` to not call `query.describe_world()` when creating events
- [x] 7.3 Remove world_context from event table structure in `Event.create()`

## 8. Python: Update Dialogue Prompt Builder

- [x] 8.1 Update `create_dialogue_request_prompt()` to query scene via state client JIT
- [x] 8.2 Build CURRENT LOCATION section from scene query response instead of event.world_context
- [x] 8.3 Call `build_world_context()` and include DYNAMIC WORLD STATE / NEWS section if non-empty

## 9. Lua: Remove Dead Code from event.lua

- [x] 9.1 Remove `TEMPLATES` table
- [x] 9.2 Remove `table_to_args()` function
- [x] 9.3 Remove `describe_object()` function
- [x] 9.4 Remove `Event.describe_event()` function
- [x] 9.5 Remove `Event.describe()` function
- [x] 9.6 Remove `Event.describe_short()` function

## 10. Lua: Remove Dead Code from game_adapter.lua

- [x] 10.1 Remove `get_mentioned_factions()` function
- [x] 10.2 Remove `is_player_involved()` function
- [x] 10.3 Remove `get_mentioned_characters()` function

## 11. Tests

- [x] 11.1 Remove Event.describe tests from `tests/entities/test_event.lua`
- [x] 11.2 Add Python tests for world_context module (26 tests)
- [x] 11.3 Run Lua test suite and fix any broken tests (7 passed)
- [x] 11.4 Run Python test suite and fix any broken tests (196 passed)

## 12. Event Model & Prompt Cleanup (Additional)

- [x] 12.1 Remove `content` field from Event model in `state/models.py` (legacy field, COMPRESSED uses context.narrative now)
- [x] 12.2 Add COMPRESSED event type handler in `prompts/helpers.py` using `context.narrative` for summary text
- [x] 12.3 Consolidate duplicate models: `prompts/models.py` now imports Character, Event, MemoryContext from `state/models.py`
- [x] 12.4 Remove `is_synthetic` property from Event (was for time gap events, now uses NarrativeCue)
- [x] 12.5 Remove `is_compressed` backward-compat handling from `prompts/builder.py`
- [x] 12.6 Create `NarrativeCue` dataclass in `prompts/models.py` for time gap artifacts (not stored)
- [x] 12.7 Add unit tests for COMPRESSED event formatting (2 tests)
- [x] 12.8 Trim integration tests to T1 only, update docstring with JSON constant structure guide
- [x] 12.9 Run full test suite (216 passed)
