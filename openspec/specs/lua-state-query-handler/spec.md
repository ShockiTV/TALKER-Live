# lua-state-query-handler

## Overview

Lua handlers that respond to Python state queries, providing access to memory_store, event_store, and character data.

## Requirements

### ADDED: Memories Query Handler

The system MUST handle `state.query {type: "memories.get", character_id}` by:
- Calling `memory_store:get_memory_context(character_id)`
- Serializing narrative + new_events to JSON
- Publishing response to `state.response` topic
- Including original request_id in response

### ADDED: Events Query Handler

The system MUST handle `state.query {type: "events.recent", since_ms, limit}` by:
- Calling `event_store:get_events_since(since_ms)`
- Optionally limiting result count
- Serializing events to JSON
- Publishing response with request_id

### ADDED: Character Query Handler

The system MUST handle `state.query {type: "character.get", character_id}` by:
- Calling `game_adapter.get_character_by_id(character_id)`
- Serializing character to JSON (name, faction, rank, personality, etc.)
- Publishing response with request_id
- Returning null if character not found

### ADDED: Nearby Characters Query Handler

The system MUST handle `state.query {type: "characters.nearby", position, radius}` by:
- Calling `game.get_characters_near(position, radius)`
- Serializing character list to JSON
- Publishing response with request_id

### ADDED: Query Response Format

All query responses MUST use format:
```json
{
  "request_id": "abc123",
  "type": "memories.get",
  "success": true,
  "data": { ... }
}
```
On error:
```json
{
  "request_id": "abc123",
  "type": "memories.get",
  "success": false,
  "error": "Character not found"
}
```

### ADDED: Memory Update Command Handler

The system MUST handle `memory.update {character_id, narrative, last_update_time_ms}` by:
- Calling `memory_store:update_narrative(character_id, narrative, time)`
- Logging the update
- No response required (fire-and-forget command)

### ADDED: Dialogue Display Command Handler

The system MUST handle `dialogue.display {speaker_id, speaker_name, text}` by:
- Calling `game_adapter.display_dialogue(speaker_id, text)`
- Creating dialogue event via `game_adapter.create_dialogue_event()`
- Storing dialogue event in event_store

## Scenarios

#### Query memories for character

WHEN Python sends memories.get query with character_id=123
THEN handler fetches memory context from memory_store
AND publishes state.response with narrative and new_events
AND response includes matching request_id

#### Query returns empty for new character

WHEN memories.get query is for character with no history
THEN response success=true with empty narrative and empty events
AND request_id matches

#### Display dialogue command

WHEN Python sends dialogue.display command
THEN game displays the dialogue via HUD
AND dialogue event is created and stored
AND event witnesses include speaker

#### Character not found

WHEN character.get query has invalid character_id
THEN response success=false
AND error message indicates "Character not found"
AND request_id matches

#### Memory update applied

WHEN Python sends memory.update command
THEN memory_store is updated with new narrative
AND update is persisted on next save
