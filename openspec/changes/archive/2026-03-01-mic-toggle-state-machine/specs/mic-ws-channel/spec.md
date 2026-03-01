## ADDED Requirements

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

## MODIFIED Requirements

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
