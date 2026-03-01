## MODIFIED Requirements

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

### Requirement: Register topic handlers

`router.register_handler(topic, fn)` SHALL store `fn` as the handler for `topic`. When a message with matching `t` arrives (and no `r` field), `asyncio.create_task(fn(payload, session_id))` SHALL be called, where `session_id` is resolved from the sending connection.

#### Scenario: Handler called with payload and session_id

- **WHEN** `"game.event"` handler is registered
- **AND** a frame with `t = "game.event"` arrives from session "alice"
- **THEN** the handler is scheduled as `handler(payload, "alice")`
