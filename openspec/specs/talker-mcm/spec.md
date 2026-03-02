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
- **THEN** it contains defaults for at least: `debug_logging`, `witness_distance`, `npc_speak_distance`, `ai_model_method`, `custom_ai_model`, `custom_ai_model_fast`, `zmq_port`, `zmq_heartbeat_interval`, `llm_timeout`, `state_query_timeout`, `language`, `input_option`, `speak_key`, `gpt_version`, `reasoning_level`, `voice_provider`, `service_url`, `ws_token`
- **AND** it SHALL contain defaults for all `triggers/*` keys: enable, cooldown, and chance per trigger type

### Requirement: MCM service_url input field

The MCM SHALL include a text input field `service_url` in the Python Service Configuration section. The default value SHALL be `wss://talker-live.duckdns.org/ws`. This field specifies the upstream talker_service WebSocket URL that the bridge connects to.

#### Scenario: Default service_url

- **WHEN** the player has not changed the `service_url` setting
- **THEN** the MCM returns `wss://talker-live.duckdns.org/ws`

#### Scenario: Player sets remote URL

- **WHEN** the player enters `wss://talker-live.duckdns.org/ws` in the `service_url` field
- **THEN** `config.get_all_config()` includes `service_url: "wss://talker-live.duckdns.org/ws"`

### Requirement: MCM ws_token input field

The MCM SHALL include a text input field `ws_token` in the Python Service Configuration section. The default value SHALL be empty string `""`. This field provides the authentication token appended to the service URL.

#### Scenario: Default ws_token is empty

- **WHEN** the player has not changed the `ws_token` setting
- **THEN** the MCM returns `""`

#### Scenario: Player sets token

- **WHEN** the player enters `invite-code-abc123` in the `ws_token` field
- **THEN** `config.get_all_config()` includes `ws_token: "invite-code-abc123"`
