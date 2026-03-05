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
- **THEN** it contains `service_ws_port` with default value 5557
- **AND** it does NOT contain `mic_ws_port`

### Requirement: MCM service_url input field

The MCM SHALL include a text input field `service_url` in the Python Service Configuration section. The default value SHALL be empty (local connection via `service_ws_port`). This field specifies the `talker_service` WebSocket URL that Lua connects to directly (no bridge intermediary).

#### Scenario: Default service_url (empty = local connection)

- **WHEN** the player has not changed the `service_url` setting
- **THEN** the MCM returns empty string
- **AND** Lua connects to `ws://127.0.0.1:<service_ws_port>/ws` (default 5557)

#### Scenario: Player sets remote URL

- **WHEN** the player enters `wss://talker-live.duckdns.org/ws` in the `service_url` field
- **THEN** Lua connects directly to the remote `talker_service`

### Requirement: MCM ws_token input field

The MCM SHALL include a text input field `ws_token` in the Python Service Configuration section. The default value SHALL be empty string `""`. This field provides the authentication token appended to the service URL.

#### Scenario: Default ws_token is empty

- **WHEN** the player has not changed the `ws_token` setting
- **THEN** the MCM returns `""`

#### Scenario: Player sets token

- **WHEN** the player enters `invite-code-abc123` in the `ws_token` field
- **THEN** `config.get_all_config()` includes `ws_token: "invite-code-abc123"`

### Requirement: MCM service_ws_port field

The MCM SHALL include a numeric input field `service_ws_port` (default 5557) in the Python Service Configuration section. This specifies the port for local `talker_service` connections when `service_url` is empty. The field is ignored when a remote `service_url` is configured.

#### Scenario: Default local port
- **WHEN** `service_url` is empty and `service_ws_port` is 5557
- **THEN** Lua connects to `ws://127.0.0.1:5557/ws`

#### Scenario: Custom local port
- **WHEN** `service_url` is empty and `service_ws_port` is 9999
- **THEN** Lua connects to `ws://127.0.0.1:9999/ws`

#### Scenario: Remote URL ignores port
- **WHEN** `service_url` is `wss://example.com/ws` and `service_ws_port` is 9999
- **THEN** Lua connects to `wss://example.com/ws` (port field ignored)
