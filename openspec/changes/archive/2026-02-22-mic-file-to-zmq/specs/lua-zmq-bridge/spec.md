## MODIFIED Requirements

### Requirement: Bridge Module

The bridge module MUST initialize unconditionally when the mod loads. There SHALL be no configuration toggle to disable ZMQ communication.

The bridge module MUST provide:
- PUB socket on port 5555 for publishing events to Python
- SUB socket connecting to Python PUB on port 5556 for receiving commands
- **Mic SUB socket connecting to mic_python PUB on port 5557 for receiving mic status/results**
- `poll_commands()` function for non-blocking receive **from both SUB sockets**
- Command handler registration
- **Tri-socket** lifecycle management
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

## ADDED Requirements

### Requirement: Mic SUB socket initialization

The bridge module SHALL initialize a third ZMQ socket: a SUB socket connecting to mic_python's PUB endpoint on tcp://127.0.0.1:5557.

#### Scenario: Mic SUB socket connects on init
- **WHEN** bridge.init() is called
- **THEN** a SUB socket SHALL connect to tcp://127.0.0.1:5557
- **AND** the socket SHALL subscribe to topics prefixed with `mic.`
- **AND** initialization SHALL NOT fail if mic_python is not running (ZMQ handles absent peers gracefully)

#### Scenario: Mic SUB socket port is configurable
- **WHEN** bridge.init(opts) is called with `opts.mic_sub_endpoint`
- **THEN** the mic SUB socket SHALL connect to the specified endpoint instead of the default

### Requirement: poll_commands polls both SUB sockets

The `poll_commands()` function SHALL poll both the primary SUB socket (talker_service on :5556) and the mic SUB socket (mic_python on :5557) in a single call.

#### Scenario: Poll processes messages from both sockets
- **WHEN** poll_commands() is called
- **THEN** it SHALL attempt non-blocking receive on the primary SUB socket
- **AND** it SHALL attempt non-blocking receive on the mic SUB socket
- **AND** messages from both sockets SHALL be dispatched to registered handlers
- **AND** the total count of processed messages from both sockets SHALL be returned

#### Scenario: Mic SUB absent does not affect primary SUB
- **WHEN** the mic SUB socket has no messages (mic_python not running)
- **THEN** poll_commands() SHALL still process messages from the primary SUB socket normally
- **AND** no errors SHALL be logged for the absent mic connection

### Requirement: Mic SUB socket shutdown

The bridge shutdown sequence SHALL close the mic SUB socket in addition to the existing PUB and primary SUB sockets.

#### Scenario: Clean shutdown with mic socket
- **WHEN** bridge.shutdown() is called
- **THEN** the mic SUB socket SHALL be closed
- **AND** the primary SUB socket SHALL be closed
- **AND** the PUB socket SHALL be closed
- **AND** all handler registrations SHALL be cleared
