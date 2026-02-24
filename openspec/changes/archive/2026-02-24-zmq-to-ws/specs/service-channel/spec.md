# service-channel

## Purpose

Lua service communication channel — lifecycle, reconnect state machine, message publishing, topic subscription, and request/response support. Fully testable via injectable socket and codec.

## Requirements

### Requirement: Initialize the channel

`channel.init(url)` SHALL store the service URL and set state to `DISCONNECTED`. Calling `init` while already initialized SHALL reset state and close any existing connection.

#### Scenario: Init stores URL

- **WHEN** `channel.init("ws://localhost:5557/ws?token=abc")` is called
- **THEN** `channel.get_status()` returns `"disconnected"`

### Requirement: Connect and maintain state machine

`channel.tick()` SHALL drive the connection lifecycle. States are `DISCONNECTED`, `CONNECTING`, `CONNECTED`, `RECONNECTING`. Transitions:
- `DISCONNECTED → CONNECTING` on first `tick()` after `init()`
- `CONNECTING → CONNECTED` when `ws_client.status(handle) == "connected"`
- `CONNECTED → RECONNECTING` when `ws_client.status(handle) == "closed"` or `"error"`
- `RECONNECTING → CONNECTING` after backoff delay expires

#### Scenario: First tick initiates connection

- **WHEN** `channel.tick()` is called after `channel.init(url)`
- **THEN** `ws_client.open(url)` is called
- **AND** state transitions to `CONNECTING`

#### Scenario: Tick detects connection established

- **WHEN** state is `CONNECTING`
- **AND** the mock socket status returns `"connected"`
- **AND** `channel.tick()` is called
- **THEN** state transitions to `CONNECTED`

#### Scenario: Tick detects disconnection

- **WHEN** state is `CONNECTED`
- **AND** the mock socket status returns `"closed"`
- **AND** `channel.tick()` is called
- **THEN** state transitions to `RECONNECTING`

#### Scenario: Reconnect fires on_reconnect callback

- **WHEN** state transitions from `CONNECTING` to `CONNECTED` after a previous `RECONNECTING` state
- **THEN** the registered `on_reconnect` callback is invoked
- **AND** `config.sync` message is published

### Requirement: Exponential backoff on reconnect

Backoff delays SHALL follow the sequence 1s, 2s, 4s, 8s, capped at 30s, with random jitter ±20%.

#### Scenario: First reconnect delay is approximately 1 second

- **WHEN** the channel enters `RECONNECTING` for the first time
- **THEN** no reconnect attempt is made for at least 0.8s
- **AND** an attempt is made within 1.2s

#### Scenario: Backoff resets after successful reconnect

- **WHEN** a reconnect attempt succeeds (`CONNECTED` state reached)
- **THEN** the next failure restarts backoff at 1s

### Requirement: Publish a message

`channel.publish(topic, payload)` SHALL encode a `{t, p}` envelope and send it over the WS connection. If the channel is not `CONNECTED`, the message SHALL be queued. The outbound queue SHALL hold at most `MAX_QUEUE_SIZE` (default 100) messages; older messages are dropped when the limit is exceeded.

#### Scenario: Publish sends encoded message when connected

- **WHEN** `channel.publish("game.event", {type="DEATH"})` is called in `CONNECTED` state
- **THEN** `ws_client.send(handle, encoded_json)` is called with the correct envelope

#### Scenario: Publish queues message when not connected

- **WHEN** `channel.publish("game.event", {})` is called in `DISCONNECTED` state
- **THEN** the message is added to the outbound queue
- **AND** `ws_client.send` is NOT called

#### Scenario: Queued messages flushed on connect

- **WHEN** the channel transitions to `CONNECTED`
- **THEN** all queued messages are sent in order

### Requirement: Subscribe to incoming topics

`channel.on(topic, fn)` SHALL register `fn` to be called with the decoded payload when a message with `t == topic` arrives. Multiple handlers per topic are allowed.

#### Scenario: Handler called on matching topic

- **WHEN** the channel receives `{"t":"dialogue.display","p":{"speaker_id":"5",...}}`
- **AND** `channel.on("dialogue.display", handler)` was registered
- **THEN** `handler({speaker_id="5",...})` is called

#### Scenario: Non-matching topic not dispatched

- **WHEN** the channel receives a message with `t = "memory.update"`
- **AND** only `channel.on("dialogue.display", handler)` is registered
- **THEN** `handler` is NOT called

### Requirement: Request/response with callback

`channel.request(topic, payload, callback)` SHALL publish the message with a generated UUID `r` field. When a response arrives with a matching `r`, `callback(response_payload)` SHALL be called. Responses with `r` set are routed to callbacks and NOT dispatched to topic handlers.

#### Scenario: Request callback invoked on matching r

- **WHEN** `channel.request("state.query.batch", {queries={}}, cb)` is called
- **AND** a response arrives with matching `r` field
- **THEN** `cb(response_payload)` is called

#### Scenario: Response with r does not trigger topic handler

- **WHEN** a response with `r` field arrives
- **AND** a handler is registered for the response's `t` topic
- **THEN** the topic handler is NOT called

### Requirement: Drain messages during tick

During each `tick()`, `channel` SHALL call `ws_client.poll(handle)` in a loop, draining up to `MAX_MESSAGES_PER_TICK` (default 20) messages. Remaining messages are left for the next tick.

#### Scenario: Tick drains multiple messages

- **WHEN** three messages are pending on the socket
- **AND** `channel.tick()` is called
- **THEN** all three are decoded and dispatched in order

### Requirement: Shutdown

`channel.shutdown()` SHALL close the WS connection, clear the outbound queue, and set state to `DISCONNECTED`.

#### Scenario: Shutdown closes socket

- **WHEN** `channel.shutdown()` is called in `CONNECTED` state
- **THEN** `ws_client.close(handle)` is called
- **AND** `channel.get_status()` returns `"disconnected"`

### Requirement: Status query

`channel.get_status()` SHALL return the current state as a lowercase string: `"disconnected"`, `"connecting"`, `"connected"`, `"reconnecting"`.

#### Scenario: Status reflects current state

- **WHEN** the channel is in `CONNECTED` state
- **THEN** `channel.get_status()` returns `"connected"`
