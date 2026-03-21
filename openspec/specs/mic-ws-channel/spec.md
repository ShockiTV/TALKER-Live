# mic-ws-channel

## Purpose

Lua mic communication channel — handle all mic-related WebSocket communication to `talker_service` over the single direct connection. Handles session-scoped handler registration for `mic.status` and `mic.result` topics, with cleanup on session completion.

## Requirements

### Requirement: Initialize and connect to mic service

`bridge_channel.init(url)` SHALL initialize with the service WS URL (not a separate mic URL). `bridge_channel.tick()` drives the state machine identically to before. The default URL SHALL be `ws://127.0.0.1:5557/ws` (the `talker_service` endpoint).

#### Scenario: Init and tick connects to service
- **WHEN** `bridge_channel.init("ws://127.0.0.1:5557/ws")` is called
- **AND** `bridge_channel.tick()` is called
- **THEN** a WS connection to the service URL is opened

### Requirement: Session-scoped handler registration

`bridge_channel.start_session(on_status, on_result)` SHALL register `on_status` and `on_result` as handlers for `mic.status` and `mic.result` for the duration of one recording session. Handlers from a previous session SHALL be cleared before registering new ones.

#### Scenario: start_session registers handlers

- **WHEN** `bridge_channel.start_session(status_fn, result_fn)` is called
- **AND** a `mic.status` message arrives
- **THEN** `status_fn(payload)` is called

#### Scenario: start_session clears previous session handlers

- **WHEN** `bridge_channel.start_session(fn_a, fn_b)` is called
- **AND** then `bridge_channel.start_session(fn_c, fn_d)` is called
- **AND** a `mic.status` message arrives
- **THEN** only `fn_c(payload)` is called, NOT `fn_a`

### Requirement: Permanent general handler registration

`bridge_channel.on(topic, handler)` SHALL register a permanent handler for a topic that persists across session boundaries. Messages matching the topic SHALL be dispatched to the permanent handler when no session-scoped handler is registered.

#### Scenario: Permanent handler receives messages

- **WHEN** `bridge_channel.on("mic.result", handler)` is called
- **AND** no session-scoped handler is registered for `mic.result`
- **AND** a `mic.result` message arrives
- **THEN** `handler(payload)` is invoked

### Requirement: Auto-cleanup on mic.result

When a `mic.result` message is received, session handlers (`on_status`, `on_result`) SHALL be cleared automatically after `on_result` is invoked.

#### Scenario: Handlers cleared after result

- **WHEN** a `mic.result` message arrives
- **AND** `on_result(payload)` has been called
- **THEN** subsequent `mic.status` messages do NOT invoke the old `on_status` handler

### Requirement: Publish to mic service

`bridge_channel.publish(topic, payload)` SHALL send a message directly to `talker_service` using the same envelope format. There is no intermediate bridge.

#### Scenario: Event published directly to service
- **WHEN** `bridge_channel.publish("game.event", {...})` is called in `CONNECTED` state
- **THEN** a properly encoded envelope is sent directly to `talker_service`

