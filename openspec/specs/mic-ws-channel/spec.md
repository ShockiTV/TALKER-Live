# mic-ws-channel

## Purpose

Lua mic communication channel — thin variant of `service-channel` for the mic_python WebSocket connection. Handles session-scoped handler registration for `mic.status` and `mic.result` topics, with cleanup on session completion.

## Requirements

### Requirement: Initialize and connect to mic service

`mic_channel.init(url)` SHALL initialize with the mic WS URL. `mic_channel.tick()` drives the state machine identically to `service-channel`.

#### Scenario: Init and tick connects to mic

- **WHEN** `mic_channel.init("ws://localhost:5558")` is called
- **AND** `mic_channel.tick()` is called
- **THEN** a WS connection to the mic URL is opened

### Requirement: Session-scoped handler registration

`mic_channel.start_session(on_status, on_result)` SHALL register `on_status` and `on_result` as handlers for `mic.status` and `mic.result` for the duration of one recording session. Handlers from a previous session SHALL be cleared before registering new ones.

NOTE: The mic recorder no longer uses `start_session()` — it registers permanent `on()` handlers instead. `start_session()` remains available for other use cases but is not used by the mic toggle state machine.

#### Scenario: start_session registers handlers

- **WHEN** `mic_channel.start_session(status_fn, result_fn)` is called
- **AND** a `mic.status` message arrives
- **THEN** `status_fn(payload)` is called

#### Scenario: start_session clears previous session handlers

- **WHEN** `mic_channel.start_session(fn_a, fn_b)` is called
- **AND** then `mic_channel.start_session(fn_c, fn_d)` is called
- **AND** a `mic.status` message arrives
- **THEN** only `fn_c(payload)` is called, NOT `fn_a`

### Requirement: Permanent general handler registration

`bridge_channel.on(topic, handler)` SHALL register a permanent handler for a topic that persists across session boundaries. Messages matching the topic SHALL be dispatched to the permanent handler when no session-scoped handler is registered.

#### Scenario: Permanent handler receives messages

- **WHEN** `bridge_channel.on("mic.result", handler)` is called
- **AND** no session-scoped handler is registered for `mic.result`
- **AND** a `mic.result` message arrives
- **THEN** `handler(payload)` is invoked

### Requirement: mic.stopped downstream topic

`mic.stopped` SHALL be a recognized downstream topic from the bridge to Lua. It notifies Lua that capture ended due to VAD silence detection (not a manual stop).

#### Scenario: mic.stopped dispatched to permanent handler

- **WHEN** `bridge_channel.on("mic.stopped", handler)` is called
- **AND** a `mic.stopped` message arrives from the bridge
- **THEN** `handler(payload)` is invoked with `{reason: "vad"}`

### Requirement: Auto-cleanup on mic.result

When a `mic.result` message is received, session handlers (`on_status`, `on_result`) SHALL be cleared automatically after `on_result` is invoked.

#### Scenario: Handlers cleared after result

- **WHEN** a `mic.result` message arrives
- **AND** `on_result(payload)` has been called
- **THEN** subsequent `mic.status` messages do NOT invoke the old `on_status` handler

### Requirement: Publish to mic service

`mic_channel.publish(topic, payload)` SHALL send a message to mic_python using the same envelope format as `service-channel`.

#### Scenario: Start recording command sent

- **WHEN** `mic_channel.publish("mic.start", {})` is called in `CONNECTED` state
- **THEN** a properly encoded envelope is sent to the mic WS connection

### Requirement: Independent lifecycle from service channel

The mic channel's connection state SHALL be fully independent of the service channel. A disconnect in one SHALL NOT affect the other.

#### Scenario: Mic disconnect does not affect service channel

- **WHEN** the mic WS connection drops
- **THEN** `service_channel.get_status()` remains `"connected"`
- **AND** `mic_channel.get_status()` transitions to `"reconnecting"`
