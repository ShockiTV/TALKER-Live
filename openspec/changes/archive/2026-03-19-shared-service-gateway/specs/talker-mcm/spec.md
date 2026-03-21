# talker-mcm (delta)

## ADDED Requirements

### Requirement: MCM Connection tab fields

The MCM SHALL include a Connection tab with the following new settings: `service_type` (radio: Local=0 / Remote=1, default 0), `service_hub_url` (text, default empty), `branch` (radio: main=0 / dev=1 / custom=2, default 0), `custom_branch` (text, default empty), `auth_username` (text, default empty), `auth_password` (text, default empty), `auth_client_id` (text, default `talker-client`), `auth_client_secret` (text, default empty), `llm_timeout` (numeric, default 60), `state_query_timeout` (numeric, default 10).

#### Scenario: New Connection fields in config defaults

- **WHEN** `require("interface.config_defaults")` is called
- **THEN** the defaults table SHALL include `service_type = 0`, `service_hub_url = ""`, `branch = 0`, `custom_branch = ""`, `auth_username = ""`, `auth_password = ""`, `auth_client_id = "talker-client"`, `auth_client_secret = ""`, `llm_timeout = 60`, `state_query_timeout = 10`

#### Scenario: Connection fields included in config.sync

- **WHEN** `config.get_all_config()` is called on game load
- **THEN** the resulting table SHALL include all Connection tab fields with their current MCM values

#### Scenario: Auth fields flow to Python via config.sync

- **WHEN** the player sets `auth_username = "player1"` and `auth_password = "secret"` in MCM
- **AND** `config.sync` is sent to Python
- **THEN** Python's `ConfigMirror` SHALL receive `auth_username = "player1"` and `auth_password = "secret"`

## MODIFIED Requirements

### Requirement: MCM service_url input field

The MCM SHALL include a text input field `service_url` in the Connection tab's Local section (moved from the former Python Service Configuration section). The default value SHALL be empty (local connection via `service_ws_port`). This field specifies the `talker_service` WebSocket URL that Lua connects to directly. When `service_type` is Remote, this field is ignored and the URL is derived from `service_hub_url` and `branch`.

#### Scenario: Default service_url (empty = local connection)

- **WHEN** the player has not changed the `service_url` setting
- **THEN** the MCM returns empty string
- **AND** Lua connects to `ws://127.0.0.1:<service_ws_port>/ws` (default 5557)

#### Scenario: Player sets remote URL directly

- **WHEN** `service_type` is Local and the player enters `ws://192.168.1.100:5557/ws` in the `service_url` field
- **THEN** Lua connects directly to that URL

#### Scenario: Remote service type ignores service_url

- **WHEN** `service_type` is Remote and `service_hub_url` is set
- **THEN** the WS URL SHALL be derived from `service_hub_url` and `branch`
- **AND** the `service_url` field SHALL be ignored

### Requirement: MCM ws_token input field

The MCM SHALL include a text input field `ws_token` in the Connection tab's Auth section (moved from the former Python Service Configuration section). The default value SHALL be empty string `""`. When `service_type` is Remote and auth credentials are configured, the `ws_token` field is superseded by the JWT obtained from ROPC — the static token is only used when ROPC credentials are not configured.

#### Scenario: Default ws_token is empty

- **WHEN** the player has not changed the `ws_token` setting
- **THEN** the MCM returns `""`

#### Scenario: ws_token used when no ROPC credentials

- **WHEN** `service_type` is Remote and `auth_username` is empty but `ws_token` is `invite-code-abc`
- **THEN** the WS URL SHALL append `?token=invite-code-abc`

#### Scenario: ROPC JWT supersedes ws_token

- **WHEN** `service_type` is Remote and both `auth_username` and `ws_token` are set
- **THEN** the ROPC-obtained JWT SHALL be used as the token, NOT the static `ws_token`

### Requirement: MCM service_ws_port field

The MCM SHALL include a numeric input field `service_ws_port` (default 5557) in the Connection tab's Local section (moved from the former Python Service Configuration section). This specifies the port for local `talker_service` connections when `service_url` is empty. The field is ignored when `service_type` is Remote or when a `service_url` is configured.

#### Scenario: Default local port

- **WHEN** `service_type` is Local, `service_url` is empty, and `service_ws_port` is 5557
- **THEN** Lua connects to `ws://127.0.0.1:5557/ws`

#### Scenario: Custom local port

- **WHEN** `service_type` is Local, `service_url` is empty, and `service_ws_port` is 9999
- **THEN** Lua connects to `ws://127.0.0.1:9999/ws`

#### Scenario: Remote service type ignores port

- **WHEN** `service_type` is Remote
- **THEN** `service_ws_port` SHALL be ignored
