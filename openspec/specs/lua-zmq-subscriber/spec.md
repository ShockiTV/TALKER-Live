# lua-zmq-subscriber

## Overview

Lua SUB socket that receives commands from Python service on port 5556, enabling bidirectional communication.

## Requirements

### ADDED: ZMQ SUB Socket

The system MUST add SUB socket to `bin/lua/infra/zmq/bridge.lua` that:
- Connects to Python PUB on tcp://127.0.0.1:5556
- Subscribes to all topics (empty string filter)
- Uses non-blocking receive to avoid game freeze
- Handles socket cleanup on shutdown

### ADDED: Command Polling

The system MUST poll for commands via game loop by:
- Adding `poll_commands()` function callable from game scripts
- Processing all pending messages in single poll call
- Returning early if no messages pending (non-blocking)
- Integrating with existing time event system

### ADDED: Topic-Based Routing

The system MUST route received messages by topic:
- Parse topic from message prefix (format: `<topic> <json-payload>`)
- Dispatch to registered handlers based on topic
- Log unknown topics without crashing

### ADDED: Command Handler Registration

The system MUST support handler registration:
- `register_command_handler(topic, handler_func)`
- Handler receives parsed payload as Lua table
- Multiple handlers per topic allowed

### ADDED: Graceful Degradation

The system MUST handle connection failures by:
- Continuing game operation if Python service unavailable
- Logging connection state changes
- Attempting reconnect on next poll (lazy reconnect)

## Scenarios

#### Receive dialogue display command

WHEN Python sends `dialogue.display {...}` message
THEN SUB socket receives the message
AND message is parsed into topic and payload
AND registered handler for dialogue.display is called

#### Non-blocking poll with no messages

WHEN poll_commands is called with no pending messages
THEN function returns immediately
AND game loop is not blocked

#### Handle unknown topic

WHEN message with unknown topic is received
THEN message is logged as warning
AND no handler is called
AND processing continues for next message

#### Python service not running

WHEN poll_commands is called but Python service is down
THEN poll returns without error
AND game continues normally

#### Multiple messages in single poll

WHEN 3 messages are pending on socket
THEN all 3 are processed in single poll_commands call
AND handlers are called in order received
