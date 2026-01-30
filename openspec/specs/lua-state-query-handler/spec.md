# lua-state-query-handler

## Purpose

Lua handlers that respond to Python state queries, providing access to memory_store, event_store, and character data.

## Requirements

### Memories Query Handler

The system MUST handle `state.query {type: "memories.get", character_id}` requests.

#### Scenario: Query memories for character
- **WHEN** Python sends memories.get query with character_id=123
- **THEN** handler fetches memory context from memory_store
- **AND** publishes state.response with narrative and new_events

#### Scenario: Query returns empty for new character
- **WHEN** memories.get query is for character with no history
- **THEN** response success=true with empty narrative and empty events

### Events Query Handler

The system MUST handle `state.query {type: "events.recent", since_ms, limit}` requests.

#### Scenario: Query recent events
- **WHEN** Python sends events.recent query
- **THEN** handler fetches events from event_store
- **AND** serializes events to JSON response

### Character Query Handler

The system MUST handle `state.query {type: "character.get", character_id}` requests.

#### Scenario: Query character successfully
- **WHEN** Python sends character.get query
- **THEN** handler fetches character via game_adapter
- **AND** serializes character to JSON response

#### Scenario: Character not found
- **WHEN** character.get query has invalid character_id
- **THEN** response success=false with error message

### Nearby Characters Query Handler

The system MUST handle `state.query {type: "characters.nearby", position, radius}` requests.

#### Scenario: Query nearby characters
- **WHEN** Python sends characters.nearby query
- **THEN** handler fetches characters near position
- **AND** serializes character list to JSON response

### Memory Update Command Handler

The system MUST handle `memory.update {character_id, narrative, last_update_time_ms}` commands.

#### Scenario: Memory update applied
- **WHEN** Lua receives memory.update command
- **THEN** memory_store updates character's narrative and last_update_time_ms

### Dialogue Display Command Handler

The system MUST handle `dialogue.display {speaker_id, speaker_name, text}` commands.

#### Scenario: Display dialogue command
- **WHEN** Python sends dialogue.display command
- **THEN** game displays the dialogue via HUD
- **AND** dialogue event is created and stored
