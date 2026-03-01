# talker-mcm

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Defaults table covers all MCM keys

The MCM defaults table SHALL include defaults for `service_url` and `ws_token` in addition to all existing keys.

#### Scenario: Defaults table covers all MCM keys
- **WHEN** the defaults table is loaded
- **THEN** it contains defaults for at least: `debug_logging`, `witness_distance`, `npc_speak_distance`, `base_dialogue_chance`, `ai_model_method`, `custom_ai_model`, `custom_ai_model_fast`, `zmq_port`, `zmq_heartbeat_interval`, `llm_timeout`, `state_query_timeout`, `language`, `input_option`, `speak_key`, `gpt_version`, `reasoning_level`, `voice_provider`, `service_url`, `ws_token`
