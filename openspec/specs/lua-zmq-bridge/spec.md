# lua-zmq-bridge

## Overview

`bin/lua/infra/zmq/bridge.lua` provides ZMQ communication with Python service. ZMQ is always required (no fallback path).

## Requirements

### Bridge Module

The bridge module MUST initialize unconditionally when the mod loads. There SHALL be no configuration toggle to disable ZMQ communication.

The bridge module MUST provide:
- PUB socket on port 5555 for publishing events to Python
- SUB socket connecting to Python PUB on port 5556 for receiving commands
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

### SUB Socket Initialization

The system MUST initialize SUB socket by:
- Connecting to tcp://127.0.0.1:5556 on init
- Subscribing to all topics (empty filter)
- Using ZMQ_NOBLOCK for non-blocking operations
- Handling connection failure gracefully

### Poll Commands Function

The system MUST provide `poll_commands()` that:
- Attempts non-blocking receive on SUB socket
- Parses topic and JSON payload from message
- Dispatches to registered handlers
- Processes all pending messages in single call
- Returns number of messages processed

### Handler Registration

The system MUST provide `register_handler(topic, func)` that:
- Stores handler function keyed by topic
- Supports multiple handlers per topic
- Handlers receive parsed payload table

### Response Publishing

The system MUST provide `publish_response(topic, payload)` that:
- Uses existing PUB socket (port 5555)
- Formats message as `{topic} {json}`
- Used for state.response messages

### Connection Status API

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

### Heartbeat Acknowledgement Handler

The Lua side SHALL register a handler for `service.heartbeat.ack` messages from Python.

#### Scenario: Heartbeat acknowledgement received
- **WHEN** Python service sends `service.heartbeat.ack` in response to a heartbeat
- **THEN** the command handler SHALL call `bridge.mark_service_alive()`
- **AND** connection status SHALL be restored to connected
- **AND** if previously disconnected, reconnect notification SHALL be triggered

### Shutdown Sequence

Shutdown MUST:
- Close SUB socket
- Close PUB socket
- Clear handler registrations

## Scenarios

#### Initialize dual sockets

WHEN bridge.init() is called
THEN PUB socket connects to port 5555
AND SUB socket connects to port 5556
AND both initializations are logged
AND initialization_time is recorded

#### Poll receives command

WHEN poll_commands() is called with pending message
THEN message is received from SUB socket
AND topic and payload are parsed
AND registered handler is invoked

#### Poll with no messages

WHEN poll_commands() is called with empty queue
THEN function returns 0
AND no handlers are invoked
AND game loop continues immediately

#### Publish state response

WHEN publish_response("state.response", data) is called
THEN response is sent via PUB socket on port 5555
AND Python SUB receives the response

#### Shutdown cleans both sockets

WHEN bridge.shutdown() is called
THEN SUB socket is closed
AND PUB socket is closed
AND handlers are cleared
