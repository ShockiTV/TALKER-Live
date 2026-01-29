## ADDED Requirements

### Requirement: Game event publishing
The publisher SHALL send game events to the Python service via ZMQ with topic `game.event`.

#### Scenario: Publish typed event
- **WHEN** `publisher.send_game_event(event)` is called with a typed Event object
- **THEN** the publisher serializes the event and sends it with topic `game.event`

#### Scenario: Event serialization
- **WHEN** an event contains Character objects in witnesses
- **THEN** the publisher serializes characters to plain tables with game_id, name, faction, experience, reputation, personality, backstory, weapon fields

### Requirement: Topic constants
The publisher SHALL define standardized topic constants for all message types.

#### Scenario: Access topic constants
- **WHEN** code references `publisher.TOPICS.GAME_EVENT`
- **THEN** the value is `"game.event"`

#### Scenario: All required topics defined
- **WHEN** publisher module is loaded
- **THEN** the following topics are defined: `GAME_EVENT`, `PLAYER_DIALOGUE`, `PLAYER_WHISPER`, `CONFIG_UPDATE`, `CONFIG_SYNC`, `HEARTBEAT`

### Requirement: Player dialogue publishing
The publisher SHALL send player dialogue input to Python with topic `player.dialogue`.

#### Scenario: Publish player chat input
- **WHEN** `publisher.send_player_dialogue(text, context)` is called
- **THEN** the publisher sends `{text: "...", context: {...}}` with topic `player.dialogue`

### Requirement: Heartbeat publishing
The publisher SHALL provide a heartbeat function for connection monitoring.

#### Scenario: Send heartbeat
- **WHEN** `publisher.send_heartbeat()` is called
- **THEN** the publisher sends `{alive: true, game_time_ms: <current_time>}` with topic `system.heartbeat`

### Requirement: Fire-and-forget semantics
The publisher SHALL never block the game loop waiting for delivery confirmation.

#### Scenario: Non-blocking publish
- **WHEN** `publisher.send_game_event(event)` is called
- **THEN** the function returns immediately without waiting for acknowledgment

#### Scenario: Publish failure does not throw
- **WHEN** ZMQ bridge is unavailable
- **THEN** publish functions return `false` without raising errors
