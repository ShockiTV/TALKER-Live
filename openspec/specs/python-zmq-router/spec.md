# python-zmq-router (MODIFIED)

## Overview

Extends existing `ZMQRouter` to add PUB socket for sending commands to Lua and request-response correlation for state queries.

## Requirements

### MODIFIED: ZMQRouter Class

The existing `ZMQRouter` class MUST be extended with:
- PUB socket on port 5556 (in addition to existing SUB on 5555)
- `publish(topic, payload)` method for sending to Lua
- Response handler registration for `state.response` topic
- Request tracking for correlation

### ADDED: PUB Socket Initialization

The system MUST initialize PUB socket by:
- Binding to tcp://127.0.0.1:5556 on startup
- Setting appropriate linger timeout on shutdown
- Logging bind success/failure

### ADDED: Publish Method

The system MUST provide `publish(topic: str, payload: dict)` that:
- Serializes payload to JSON
- Sends message as `{topic} {json}` format
- Returns success/failure boolean
- Logs published messages at debug level

### ADDED: Response Handler Integration

The system MUST handle state.response messages by:
- Registering internal handler for state.response topic
- Forwarding to StateQueryClient for correlation
- Not exposing raw responses to user handlers

### MODIFIED: Shutdown Sequence

The existing shutdown MUST be modified to:
- Close PUB socket before SUB socket
- Wait for pending publishes to flush
- Log both socket closures

## Scenarios

#### Initialize with both sockets

WHEN ZMQRouter starts
THEN SUB socket connects to port 5555
AND PUB socket binds to port 5556
AND both connections are logged

#### Publish command to Lua

WHEN publish("dialogue.display", {...}) is called
THEN message is sent on PUB socket
AND Lua SUB receives the message

#### Handle state response

WHEN state.response message is received
THEN message is routed to StateQueryClient
AND user handlers for state.response are NOT called
AND correlation completes

#### Graceful shutdown

WHEN shutdown() is called
THEN pending publishes are flushed
AND PUB socket is closed
AND SUB socket is closed
AND "stopped" is logged
