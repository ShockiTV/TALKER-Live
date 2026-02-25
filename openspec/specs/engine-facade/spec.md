# engine-facade

## Purpose

Defines the engine facade module that abstracts all STALKER engine API calls behind a testable interface for bin/lua/ modules.

## Requirements

### Requirement: Engine facade module exists at interface/engine.lua

The system SHALL provide a single Lua module at `interface/engine.lua` that wraps all STALKER engine globals behind a mockable API. No `bin/lua/` module SHALL reference engine globals (`talker_mcm`, `talker_game_queries`, `talker_game_commands`, `talker_game_async`, `talker_game_files`, `ini_file`, `printf`) directly.

#### Scenario: Module loads without engine present
- **WHEN** `require("interface.engine")` is called outside the STALKER engine (engine globals are nil)
- **THEN** the module loads successfully without error

#### Scenario: Module loads with engine present
- **WHEN** `require("interface.engine")` is called inside the STALKER engine (globals are set)
- **THEN** the module loads successfully and delegates to engine globals

### Requirement: Lazy binding to engine globals

The facade SHALL use lazy binding (function calls to resolve globals) rather than capturing globals at module load time. This ensures the facade works regardless of script loading order.

#### Scenario: Global set after facade is required
- **WHEN** `require("interface.engine")` is called before `talker_game_queries` is set
- **AND** `talker_game_queries` is set afterward
- **THEN** subsequent calls to `engine.get_name(obj)` delegate to `talker_game_queries.get_name(obj)`

#### Scenario: Global never set (test environment)
- **WHEN** `talker_game_queries` is never set
- **THEN** calls to engine functions return safe defaults (false, nil, "Unknown", 0, etc.) without error

### Requirement: Facade covers MCM config access

The facade SHALL expose `engine.get_mcm_value(key)` that reads from `talker_mcm.get(key)`.

#### Scenario: MCM available
- **WHEN** `talker_mcm` global exists
- **AND** `engine.get_mcm_value("witness_distance")` is called
- **THEN** it returns the value from `talker_mcm.get("witness_distance")`

#### Scenario: MCM unavailable
- **WHEN** `talker_mcm` global is nil
- **AND** `engine.get_mcm_value("witness_distance")` is called
- **THEN** it returns nil without error

### Requirement: Facade covers game queries

The facade SHALL expose wrapper functions for all `talker_game_queries` functions that are called by `bin/lua/` modules. At minimum: `get_name`, `get_id`, `is_alive`, `get_faction`, `get_rank`, `is_player`, `is_stalker`, `is_companion`, `is_in_combat`, `are_enemies`, `get_relations`, `get_player`, `is_player_alive`, `get_player_weapon`, `get_weapon`, `get_nearby_characters`, `get_companions`, `get_position`, `get_obj_by_id`, `get_technical_name`, `get_technical_name_by_id`, `is_unique_character_by_id`, `get_unique_character_personality`, `get_location_name`, `get_location_technical_name`, `get_game_time_ms`, `iterate_nearest`, `is_living_character`, `get_distance_between`, `load_xml`, `load_random_xml`, `describe_mutant`, `describe_world`, `describe_current_time`, `get_enemies_fighting_player`, `is_psy_storm_ongoing`, `is_surge_ongoing`, `get_community_goodwill`, `get_community_relation`, `get_real_player_faction`, `get_rank_value`, `get_reputation_tier`, `get_story_id`, `get_character_event_info`.

#### Scenario: Query function delegates to engine
- **WHEN** `talker_game_queries` is available
- **AND** `engine.get_name(obj)` is called
- **THEN** it returns `talker_game_queries.get_name(obj)`

#### Scenario: Query function without engine
- **WHEN** `talker_game_queries` is nil
- **AND** `engine.get_name(obj)` is called
- **THEN** it returns `"Unknown"` without error

### Requirement: Facade covers game commands

The facade SHALL expose wrapper functions for `talker_game_commands` functions used by `bin/lua/` modules: `display_message`, `display_hud_message`, `send_news_tip`, `play_sound`, `SendScriptCallback`.

#### Scenario: Command function delegates to engine
- **WHEN** `talker_game_commands` is available
- **AND** `engine.display_hud_message("test")` is called
- **THEN** it calls `talker_game_commands.display_hud_message("test")`

#### Scenario: Command function without engine
- **WHEN** `talker_game_commands` is nil
- **AND** `engine.display_hud_message("test")` is called
- **THEN** it does nothing without error

### Requirement: Facade covers async and file operations

The facade SHALL expose `engine.repeat_until_true(...)` wrapping `talker_game_async` and `engine.get_base_path()` wrapping `talker_game_files`.

#### Scenario: Async available
- **WHEN** `talker_game_async` is available
- **AND** `engine.repeat_until_true(fn, interval)` is called
- **THEN** it delegates to `talker_game_async.repeat_until_true(fn, interval)`

#### Scenario: Base path without engine
- **WHEN** `talker_game_files` is nil
- **AND** `engine.get_base_path()` is called
- **THEN** it returns `""` (empty string)

### Requirement: Facade covers time events and callbacks

The facade SHALL expose `engine.create_time_event(...)`, `engine.reset_time_event(...)`, and `engine.register_callback(name, handler)` wrapping their engine equivalents.

#### Scenario: Time event creation
- **WHEN** engine is available
- **AND** `engine.create_time_event("ev", "act", 5, fn)` is called
- **THEN** it calls `CreateTimeEvent("ev", "act", 5, fn)`

#### Scenario: Callback registration without engine
- **WHEN** engine is not available
- **AND** `engine.register_callback("actor_on_death", fn)` is called
- **THEN** it does nothing without error

### Requirement: All bin/lua modules use facade instead of globals

After migration, no file in `bin/lua/` SHALL contain direct references to `talker_mcm`, `talker_game_queries`, `talker_game_commands`, `talker_game_async`, or `talker_game_files` as globals. All access SHALL go through `require("interface.engine")`.

#### Scenario: config.lua uses facade
- **WHEN** `interface/config.lua` reads an MCM value
- **THEN** it calls `engine.get_mcm_value(key)` instead of `talker_mcm.get(key)`

#### Scenario: logger.lua uses facade
- **WHEN** `framework/logger.lua` checks debug logging mode
- **THEN** it calls `engine.get_mcm_value("debug_logging")` instead of `talker_mcm.get("debug_logging")`

#### Scenario: game_adapter.lua uses facade
- **WHEN** `infra/game_adapter.lua` queries a game object
- **THEN** it calls `engine.get_name(obj)` (or similar) instead of `talker_game_queries.get_name(obj)`

#### Scenario: backstories.lua uses facade
- **WHEN** `domain/repo/backstories.lua` checks if a character is unique
- **THEN** it calls `engine.is_unique_character_by_id(id)` instead of `talker_game_queries.is_unique_character_by_id(id)`

### Requirement: Logger error does not cascade to game adapter

`logger.error()` SHALL NOT trigger a require of `infra.game_adapter` that could cascade into engine dependencies. The display-to-player call SHALL be guarded with pcall or conditionally executed.

#### Scenario: log.error in test environment
- **WHEN** `log.error("something failed")` is called outside the game engine
- **THEN** the error is written to log file and/or printed
- **AND** no error is raised from attempting to load game_adapter

#### Scenario: log.error in game environment
- **WHEN** `log.error("something failed")` is called inside the game engine
- **THEN** the error is written to log file, printed, and displayed to the player via HUD
