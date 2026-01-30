# lua-zmq-subscriber

## Purpose

Lua SUB socket that receives commands from Python service on port 5556, enabling bidirectional communication.

## Requirements

### ZMQ SUB Socket

The system MUST add SUB socket to `bin/lua/infra/zmq/bridge.lua` for receiving Python commands.

#### Scenario: SUB socket connects on init
- **WHEN** bridge.init() is called
- **THEN** SUB socket connects to Python PUB on tcp://127.0.0.1:5556
- **AND** socket subscribes to all topics

### Command Polling

The system MUST poll for commands via game loop using non-blocking receive.

#### Scenario: Non-blocking poll with no messages
- **WHEN** poll_commands is called with no pending messages
- **THEN** function returns immediately
- **AND** game loop is not blocked

#### Scenario: Multiple messages in single poll
- **WHEN** 3 messages are pending on socket
- **THEN** all 3 are processed in single poll_commands call

### Topic-Based Routing

The system MUST route received messages by topic to registered handlers.

#### Scenario: Receive dialogue display command
- **WHEN** Python sends `dialogue.display {...}` message
- **THEN** message is parsed into topic and payload
- **AND** registered handler for dialogue.display is called

#### Scenario: Handle unknown topic
- **WHEN** message with unknown topic is received
- **THEN** message is logged as warning
- **AND** processing continues for next message

### Command Handler Registration

The system MUST support handler registration via `register_command_handler(topic, handler_func)`.

#### Scenario: Handler registration
- **WHEN** register_command_handler(topic, func) is called
- **THEN** handler receives parsed payload when topic message arrives

### Graceful Degradation

The system MUST handle connection failures gracefully.

#### Scenario: Python service not running
- **WHEN** poll_commands is called but Python service is down
- **THEN** poll returns without error
- **AND** game continues normally
