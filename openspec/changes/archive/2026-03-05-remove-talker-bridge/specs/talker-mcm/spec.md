# talker-mcm

## MODIFIED Requirements

### Requirement: MCM defaults available as pure Lua module

The MCM defaults table SHALL contain `service_ws_port` (default 5557) instead of `mic_ws_port` (default 5558). The `service_ws_port` field specifies the port for local `talker_service` connections.

#### Scenario: Defaults table covers all MCM keys
- **WHEN** the defaults table is loaded
- **THEN** it contains `service_ws_port` with default value 5557
- **AND** it does NOT contain `mic_ws_port`

### Requirement: MCM service_url input field

The MCM SHALL include a text input field `service_url` in the Python Service Configuration section. The default value SHALL be `wss://talker-live.duckdns.org/ws`. This field specifies the `talker_service` WebSocket URL that Lua connects to directly (no bridge intermediary).

#### Scenario: Default service_url
- **WHEN** the player has not changed the `service_url` setting
- **THEN** the MCM returns `wss://talker-live.duckdns.org/ws`

#### Scenario: Player sets local URL
- **WHEN** the player enters `ws://127.0.0.1:5557/ws` in the `service_url` field
- **THEN** Lua connects directly to the local `talker_service`

## RENAMED Requirements

### Requirement: MCM mic_ws_port field
FROM: `mic_ws_port` (default 5558)
TO: `service_ws_port` (default 5557)
