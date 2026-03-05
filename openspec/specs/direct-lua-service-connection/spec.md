# direct-lua-service-connection

## Purpose

Defines how the Lua game client connects directly to the Python `talker_service` over WebSocket without an intermediate bridge proxy. Removed the `talker_bridge` process entirely.

## Requirements

### Requirement: Lua connects directly to talker_service

The Lua game client SHALL connect directly to `talker_service` via a single WebSocket connection. The connection target SHALL be determined by the MCM `service_url` field. When `service_url` is empty or unset, the default connection SHALL be `ws://127.0.0.1:<service_ws_port>/ws` where `service_ws_port` defaults to 5557. When `service_url` contains a full URL (with `://`), it SHALL be used as-is with the `ws_token` appended as `?token=<value>` if non-empty.

#### Scenario: Default local connection
- **WHEN** MCM `service_url` is empty and `service_ws_port` is 5557
- **THEN** Lua connects to `ws://127.0.0.1:5557/ws`

#### Scenario: Remote URL from MCM
- **WHEN** MCM `service_url` is `wss://talker-live.duckdns.org/ws` and `ws_token` is `abc123`
- **THEN** Lua connects to `wss://talker-live.duckdns.org/ws?token=abc123`

#### Scenario: Remote URL without token
- **WHEN** MCM `service_url` is `wss://talker-live.duckdns.org/ws` and `ws_token` is empty
- **THEN** Lua connects to `wss://talker-live.duckdns.org/ws`

### Requirement: No bridge process required

The system SHALL function without `talker_bridge` running. There SHALL be no `launch_talker_bridge.bat` script and no `talker_bridge/` directory in the project. The only required external service is `talker_service`.

#### Scenario: System operates without bridge
- **WHEN** only `talker_service` is running on port 5557
- **AND** Lua connects directly to `ws://127.0.0.1:5557/ws`
- **THEN** all game events, dialogue, TTS audio, state queries, and mic audio flow correctly

### Requirement: URL construction in talker_ws_integration

The `talker_ws_integration.script` SHALL construct the service URL using MCM config values. The function SHALL be named `get_service_url()`. When `service_url` is a full URL (contains `://`), the `service_ws_port` field SHALL be ignored. When `service_url` is empty, the URL SHALL be built from `ws_host` and `service_ws_port`.

#### Scenario: Full URL ignores port field
- **WHEN** MCM `service_url` is `wss://example.com/ws` and `service_ws_port` is 9999
- **THEN** the connection URL is `wss://example.com/ws` (port field ignored)

#### Scenario: Empty service_url uses host and port
- **WHEN** MCM `service_url` is empty, `ws_host` is `127.0.0.1`, `service_ws_port` is 5557
- **THEN** the connection URL is `ws://127.0.0.1:5557/ws`
