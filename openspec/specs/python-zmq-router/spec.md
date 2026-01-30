# python-zmq-router

## Purpose

Python ZMQ router with PUB/SUB sockets for bidirectional communication with Lua game client.

## Requirements

### ZMQRouter Class

The ZMQRouter class MUST provide bidirectional communication with PUB and SUB sockets.

#### Scenario: Initialize with both sockets
- **WHEN** ZMQRouter starts
- **THEN** SUB socket connects to port 5555
- **AND** PUB socket binds to port 5556

### PUB Socket Initialization

The system MUST initialize PUB socket on port 5556 for sending commands to Lua.

#### Scenario: PUB socket binds
- **WHEN** router starts
- **THEN** PUB socket binds to tcp://127.0.0.1:5556

### Publish Method

The system MUST provide `publish(topic: str, payload: dict)` for sending messages.

#### Scenario: Publish command to Lua
- **WHEN** publish("dialogue.display", {...}) is called
- **THEN** message is sent on PUB socket
- **AND** Lua SUB receives the message

### Response Handler Integration

The system MUST handle state.response messages and forward to StateQueryClient.

#### Scenario: Handle state response
- **WHEN** state.response message is received
- **THEN** message is routed to StateQueryClient
- **AND** correlation completes

### Shutdown Sequence

The shutdown MUST close both sockets and flush pending publishes.

#### Scenario: Graceful shutdown
- **WHEN** shutdown() is called
- **THEN** pending publishes are flushed
- **AND** both sockets are closed
