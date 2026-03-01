# python-ws-router

## Purpose

Python WebSocket router providing bidirectional communication with the Lua game client. Replaces `ZMQRouter` with a FastAPI WebSocket endpoint. Handles JSON envelope routing, request/response short-circuit, and handler dispatch for all inbound topics.

## Requirements

### Requirement: Accept WebSocket connections

The `WSRouter` SHALL register a FastAPI WebSocket route at `/ws`. Each connection SHALL be upgraded via `websocket.accept()`. Token validation SHALL occur before `accept()` if `TALKER_TOKENS` is configured (see `service-token-auth` spec); unauthorized connections are rejected with close code 4001.

#### Scenario: Valid connection accepted

- **WHEN** a WebSocket client connects to `/ws` with a valid token
- **THEN** the connection is accepted
- **AND** the client can send and receive messages

#### Scenario: Connection without token rejected when auth is configured

- **WHEN** `TALKER_TOKENS` is set
- **AND** a client connects without a `?token=` query param
- **THEN** the connection is closed with code 4001
- **AND** no messages are processed

### Requirement: Parse incoming JSON envelope

For each received text frame, `WSRouter` SHALL parse the envelope using `json.loads`. The `t` field is the topic, `p` is the payload, `r` is the optional request ID. Malformed frames (not JSON or missing `t`) SHALL be logged and discarded.

#### Scenario: Valid envelope dispatched to handler

- **WHEN** `{"t":"game.event","p":{"event":{}}}` is received
- **AND** a handler is registered for `"game.event"`
- **THEN** the handler is called with `{"event":{}}`

#### Scenario: Malformed frame discarded

- **WHEN** `"not json"` is received
- **THEN** an error is logged
- **AND** no handler is called

#### Scenario: Missing t field discarded

- **WHEN** `{"p":{}}` is received (no `t` key)
- **THEN** the frame is discarded with a warning log

### Requirement: Request/response short-circuit via r field

**WHEN** an incoming frame has an `r` field, `WSRouter` SHALL resolve the corresponding `asyncio.Future` in `pending_requests[r]` with the payload value, and SHALL NOT dispatch to any topic handler.

#### Scenario: r field resolves pending future

- **WHEN** a pending future exists for `r = "req-1"`
- **AND** a frame `{"t":"state.response","p":{...},"r":"req-1"}` arrives
- **THEN** `pending_requests["req-1"].set_result(payload)` is called
- **AND** the "state.response" topic handler is NOT invoked

#### Scenario: r field with no pending future logs warning

- **WHEN** a frame with `r = "unknown-id"` arrives
- **AND** no pending future exists for that ID
- **THEN** a warning is logged and the frame is discarded

### Requirement: Register topic handlers

`router.register_handler(topic, fn)` SHALL store `fn` as the handler for `topic`. When a message with matching `t` arrives (and no `r` field), `asyncio.create_task(fn(payload, session_id))` SHALL be called, where `session_id` is resolved from the sending connection.

#### Scenario: Handler called for registered topic

- **WHEN** `"dialogue.display"` handler is registered
- **AND** a frame with `t = "dialogue.display"` arrives
- **THEN** the handler is scheduled as an asyncio task

#### Scenario: Handler called with payload and session_id

- **WHEN** `"game.event"` handler is registered
- **AND** a frame with `t = "game.event"` arrives from session "alice"
- **THEN** the handler is scheduled as `handler(payload, "alice")`

### Requirement: Publish a message to the game client

`router.publish(topic, payload, *, r=None, session=None)` SHALL encode the envelope and send it. When `session` is `None`, the message SHALL be broadcast to all connected clients (current behavior). When `session` is provided, the message SHALL be sent only to the connection for that session_id. If no clients are connected and session is None, the call is a no-op (no error).

#### Scenario: Publish sends to connected client

- **WHEN** a client is connected
- **AND** `router.publish("dialogue.display", {...})` is called
- **THEN** the client receives `{"t":"dialogue.display","p":{...}}`

#### Scenario: Publish with no clients is no-op

- **WHEN** no clients are connected
- **AND** `router.publish("dialogue.display", {...})` is called without session
- **THEN** no exception is raised

#### Scenario: Targeted publish to specific session

- **WHEN** `router.publish("dialogue.display", {...}, session="alice")` is called
- **AND** alice's connection is active
- **THEN** only alice's connection receives the message

### Requirement: Graceful shutdown

`router.stop()` SHALL close all active WebSocket connections with close code 1001 and cancel the receive loop task.

#### Scenario: Stop closes active connections

- **WHEN** `router.stop()` is called with one active client
- **THEN** the connection is closed with code 1001
