## ADDED Requirements

### Requirement: Integration script delegates lifecycle to service-channel

`talker_ws_integration.script` SHALL be the only game callback file for WS lifecycle. It SHALL register time events that call `service_channel.tick()` and `mic_channel.tick()` (via engine facade), display HUD status, and handle game load/unload events. It SHALL NOT contain connection logic, message parsing, backoff, or WS socket operations.

#### Scenario: Script registers tick timer

- **WHEN** the game actor spawns (`actor_on_update` or equivalent)
- **THEN** a time event is registered that calls `talker_ws_integration.talker_service_tick()` at ~5ms interval
- **AND** `talker_service_tick()` delegates to `infra.service.channel.tick()`

#### Scenario: Script displays status via HUD

- **WHEN** `service_channel.get_status()` changes to `"connected"`
- **THEN** the script calls `engine.set_hud_message("Service: Connected")`
- **AND** no connection logic is performed in the script itself

#### Scenario: Script triggers config.sync on game load

- **WHEN** the game fires the `on_game_load` callback
- **THEN** the script calls `service_channel.publish("config.sync", config.get_full_config())`

#### Scenario: Script shuts down channels on game unload

- **WHEN** the game fires the `on_game_unload` callback
- **THEN** the script calls `service_channel.shutdown()`
- **AND** the script calls `mic_channel.shutdown()`

## REMOVED Requirements

### Requirement: Scripts delegate pure logic to bin/lua modules (ZMQ variant)

**Reason**: The ZMQ integration script (`talker_zmq_integration.script`) is deleted. Its lifecycle logic moves to `bin/lua/infra/service/channel.lua` (fully testable). The ZMQ-specific delegation requirement is superseded by the new integration script requirement above.

**Migration**: Replace `talker_zmq_integration.script` with `talker_ws_integration.script`. The new script delegates to `infra.service.channel` via engine facade.
