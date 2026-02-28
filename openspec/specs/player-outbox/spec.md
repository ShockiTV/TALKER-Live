# player-outbox

## Purpose

Per-session message buffer that holds outbound messages during disconnection and drains on reconnect with configurable TTL.

## Requirements

### Requirement: Outbox accumulates messages during disconnection

Each session SHALL have an `Outbox` that stores outbound messages when the session has no active WebSocket connection. Messages SHALL be stored in insertion order.

#### Scenario: Message buffered when session disconnected

- **WHEN** session "alice" has no active connection
- **AND** `publish("dialogue.display", payload, session="alice")` is called
- **THEN** the message SHALL be added to alice's outbox
- **AND** the outbox size SHALL increase by 1

#### Scenario: Multiple messages buffered in order

- **WHEN** session "alice" is disconnected
- **AND** three messages are published to alice in order (msg1, msg2, msg3)
- **THEN** alice's outbox SHALL contain [msg1, msg2, msg3] in that order

### Requirement: Outbox drains on reconnect

When a session reconnects (new WebSocket connection), all messages in the outbox SHALL be sent to the new connection in insertion order, then the outbox SHALL be cleared.

#### Scenario: Reconnect drains buffered messages

- **WHEN** session "alice" has 3 messages in the outbox
- **AND** alice reconnects with a new WebSocket
- **THEN** all 3 messages SHALL be sent to the new connection in order
- **AND** the outbox SHALL be empty after draining

#### Scenario: New messages during drain go to connection directly

- **WHEN** session "alice" reconnects and the outbox is draining
- **AND** a new message is published to alice after drain completes
- **THEN** the new message SHALL be sent directly to the active connection
- **AND** the new message SHALL NOT go through the outbox

### Requirement: TTL-based message expiration

Messages in the outbox SHALL have a creation timestamp. When draining, messages older than the configured TTL SHALL be discarded. The default TTL SHALL be 30 minutes.

#### Scenario: Fresh messages delivered on drain

- **WHEN** session "alice" has messages that are 5 minutes old
- **AND** TTL is 30 minutes
- **AND** alice reconnects
- **THEN** all messages SHALL be delivered

#### Scenario: Stale messages discarded on drain

- **WHEN** session "alice" has messages that are 45 minutes old
- **AND** TTL is 30 minutes
- **AND** alice reconnects
- **THEN** the stale messages SHALL be discarded
- **AND** they SHALL NOT be sent to the connection

#### Scenario: Mixed fresh and stale messages

- **WHEN** alice's outbox has 2 stale messages (40 min old) and 3 fresh messages (2 min old)
- **AND** alice reconnects
- **THEN** only the 3 fresh messages SHALL be delivered
- **AND** the 2 stale messages SHALL be discarded

### Requirement: Max outbox size with FIFO eviction

The outbox SHALL have a configurable maximum size (default: 500 messages). When a new message would exceed the max size, the oldest message SHALL be evicted before the new message is added.

#### Scenario: Oldest message evicted at capacity

- **WHEN** alice's outbox has 500 messages (at capacity)
- **AND** a new message is published
- **THEN** the oldest message SHALL be removed
- **AND** the new message SHALL be added
- **AND** the outbox size SHALL remain 500

### Requirement: Outbox configurable via service settings

The outbox TTL and max size SHALL be configurable via service-level settings (environment variables or Settings class), not per-session MCM config.

#### Scenario: Custom TTL from settings

- **WHEN** the service is configured with `OUTBOX_TTL_MINUTES=60`
- **THEN** outbox messages SHALL expire after 60 minutes instead of the default 30
