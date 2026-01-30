# lua-zmq-bridge (MODIFIED)

## Overview

Extends existing `bin/lua/infra/zmq/bridge.lua` to add SUB socket for receiving commands from Python.

## Requirements

### MODIFIED: Bridge Module

The existing bridge module MUST be extended with:
- SUB socket connecting to Python PUB on port 5556
- `poll_commands()` function for non-blocking receive
- Command handler registration
- Dual-socket lifecycle management

### ADDED: SUB Socket Initialization

The system MUST initialize SUB socket by:
- Connecting to tcp://127.0.0.1:5556 on init
- Subscribing to all topics (empty filter)
- Using ZMQ_NOBLOCK for non-blocking operations
- Handling connection failure gracefully

### ADDED: Poll Commands Function

The system MUST provide `poll_commands()` that:
- Attempts non-blocking receive on SUB socket
- Parses topic and JSON payload from message
- Dispatches to registered handlers
- Processes all pending messages in single call
- Returns number of messages processed

### ADDED: Handler Registration

The system MUST provide `register_handler(topic, func)` that:
- Stores handler function keyed by topic
- Supports multiple handlers per topic
- Handlers receive parsed payload table

### ADDED: Response Publishing

The system MUST provide `publish_response(topic, payload)` that:
- Uses existing PUB socket (port 5555)
- Formats message as `{topic} {json}`
- Used for state.response messages

### MODIFIED: Shutdown Sequence

The existing shutdown MUST be modified to:
- Close SUB socket (new)
- Close PUB socket (existing)
- Clear handler registrations

## Scenarios

#### Initialize dual sockets

WHEN bridge.init() is called
THEN PUB socket connects to port 5555 (existing)
AND SUB socket connects to port 5556 (new)
AND both initializations are logged

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
