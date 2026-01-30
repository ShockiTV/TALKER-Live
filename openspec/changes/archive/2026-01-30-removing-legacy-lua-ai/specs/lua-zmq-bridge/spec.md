## REMOVED Requirements

### Requirement: Optional initialization based on config
**Reason**: ZMQ is now always required - there is no fallback path
**Migration**: Remove all conditional checks for `config.zmq_enabled()` - ZMQ always initializes

### Requirement: Graceful fallback when ZMQ disabled
**Reason**: No fallback behavior exists anymore - Python service is mandatory
**Migration**: Remove fallback code paths, ZMQ failure is now a hard error (with user notification)

## MODIFIED Requirements

### Requirement: Bridge Module
The bridge module MUST initialize unconditionally when the mod loads. There SHALL be no configuration toggle to disable ZMQ communication.

The existing bridge module MUST be extended with:
- SUB socket connecting to Python PUB on port 5556
- `poll_commands()` function for non-blocking receive
- Command handler registration
- Dual-socket lifecycle management
- Connection status tracking for user notifications

#### Scenario: Bridge initializes on mod load
- **WHEN** the mod loads
- **THEN** ZMQ bridge SHALL initialize automatically
- **AND** initialization SHALL NOT depend on any MCM toggle
- **AND** `initialization_time` SHALL be recorded for timeout tracking

#### Scenario: Bridge tracks connection status
- **WHEN** the bridge detects Python service is unreachable (no messages for 15 seconds)
- **THEN** the connection status SHALL be set to disconnected
- **AND** the status SHALL be queryable by other modules via `get_connection_status()`
- **AND** timeout SHALL be calculated from `last_successful_recv` or `initialization_time` if no messages received

#### Scenario: Bridge detects service recovery
- **WHEN** `poll_commands()` successfully receives a message after being disconnected
- **THEN** `mark_service_alive()` SHALL set connection status to connected
- **AND** recovery notification logic SHALL be triggered via `should_notify_reconnect()`

### Requirement: Connection Status API
The bridge module SHALL expose the following functions for connection tracking:

- `get_connection_status()` - Returns table with `connected`, `last_successful_recv`, `initialization_time`, `has_notified_disconnect`
- `mark_service_alive()` - Called when message received, sets connected=true
- `mark_service_disconnected()` - Called when timeout detected
- `should_notify_disconnect()` - Returns true once per disconnect cycle
- `should_notify_reconnect()` - Returns true once per reconnect cycle
- `reset_notification_state()` - Resets notification flags
- `is_service_available()` - Returns true if connected and initialized
- `should_notify_offline_attempt()` - Returns true (throttled) when offline and user attempts to use service

#### Scenario: Offline attempt notification
- **WHEN** the user attempts to trigger dialogue while service is disconnected
- **THEN** `should_notify_offline_attempt()` SHALL return true (max once per 10 seconds)
- **AND** the integration script SHALL display a HUD message informing user to start the service

### Requirement: Heartbeat Acknowledgement Handler
The Lua side SHALL register a handler for `service.heartbeat.ack` messages from Python.

#### Scenario: Heartbeat acknowledgement received
- **WHEN** Python service sends `service.heartbeat.ack` in response to a heartbeat
- **THEN** the command handler SHALL call `bridge.mark_service_alive()`
- **AND** connection status SHALL be restored to connected
- **AND** if previously disconnected, reconnect notification SHALL be triggered
