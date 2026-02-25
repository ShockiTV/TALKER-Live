# talker-mcm

## Purpose

Defines the Mod Configuration Menu (MCM) settings and defaults for the TALKER mod.

## Requirements

### Requirement: MCM defaults available as pure Lua module

The MCM defaults table SHALL be extracted to `interface/config_defaults.lua` as a pure Lua module with no engine dependencies. The `talker_mcm.script` defaults and `interface/config.lua` fallback values SHALL both reference this single source of truth.

#### Scenario: Config defaults load without engine
- **WHEN** `require("interface.config_defaults")` is called outside the game engine
- **THEN** it returns a table of all MCM default values

#### Scenario: Config uses defaults as fallback
- **WHEN** `interface/config.lua` calls `engine.get_mcm_value(key)` and it returns nil
- **THEN** the config getter returns the default from `config_defaults`

#### Scenario: Defaults table covers all MCM keys
- **WHEN** the defaults table is loaded
- **THEN** it contains defaults for at least: `debug_logging`, `witness_distance`, `npc_speak_distance`, `base_dialogue_chance`, `ai_model_method`, `custom_ai_model`, `custom_ai_model_fast`, `zmq_port`, `zmq_heartbeat_interval`, `llm_timeout`, `state_query_timeout`, `language`, `input_option`, `speak_key`, `gpt_version`, `reasoning_level`, `voice_provider`
