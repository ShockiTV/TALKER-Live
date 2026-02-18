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

### Characters Alive Query Handler

The system SHALL handle `state.query {type: "characters.alive", ids: [...]}` requests.

#### Scenario: Query characters alive status
- **WHEN** Python sends characters.alive query with ids=["id1", "id2"]
- **THEN** handler iterates over IDs
- **AND** for each ID, finds server object via `get_story_object(id)`
- **AND** checks alive status with fallback logic
- **AND** publishes state.response with mapping {id1: true, id2: false}

#### Scenario: Alive check uses sobj:alive() when available
- **WHEN** server object has `alive` as a function
- **THEN** calls `sobj:alive()` to determine alive status

#### Scenario: Alive check falls back to squad npc_count
- **WHEN** server object does not have `alive` function
- **AND** object clsid is `online_offline_group_s` (squad)
- **THEN** checks `npc_count` (method or property depending on engine)
- **AND** if npc_count == 0, character is dead

#### Scenario: Unknown ID returns false
- **WHEN** characters.alive query includes non-existent story_id
- **THEN** that ID maps to false in response

#### Scenario: Empty IDs list returns empty map
- **WHEN** characters.alive query with ids=[]
- **THEN** response contains empty object {}

### World Context Query Handler

The system SHALL handle `state.query {type: "world.context"}` requests and return structured scene data.

Response SHALL include:
- `loc`: Technical location ID (e.g., "l01_escape")
- `poi`: Nearby smart terrain name or null
- `time`: Object with {Y, M, D, h, m, s, ms} integer fields
- `weather`: Weather string
- `emission`: Boolean - emission active
- `psy_storm`: Boolean - psy storm active
- `sheltering`: Boolean - player is sheltering
- `campfire`: "lit" | "unlit" | null
- `brain_scorcher_disabled`: Boolean (true if has_alife_info("sar_ozerki_switcher_on"))
- `miracle_machine_disabled`: Boolean (true if has_alife_info("sar2_monolith_peace"))

#### Scenario: Query world context returns full structure
- **WHEN** Python sends world.context query
- **THEN** response includes all required fields
- **AND** time is object not array

#### Scenario: Time returned as object
- **WHEN** world.context query is processed
- **THEN** time field is {"Y": 2012, "M": 9, "D": 15, "h": 8, "m": 30, "s": 45, "ms": 123}
- **AND** not an array like [2012, 9, 15, 8, 30, 45, 123]

#### Scenario: No poi when not near smart terrain
- **WHEN** player is not near a named smart terrain
- **THEN** poi field is null

#### Scenario: Campfire null when none nearby
- **WHEN** player is not near a campfire
- **THEN** campfire field is null

#### Scenario: Brain Scorcher status included
- **WHEN** Python sends world.context query
- **THEN** response includes brain_scorcher_disabled boolean
- **AND** value is true if has_alife_info("sar_ozerki_switcher_on")

#### Scenario: Miracle Machine status included
- **WHEN** Python sends world.context query
- **THEN** response includes miracle_machine_disabled boolean
- **AND** value is true if has_alife_info("sar2_monolith_peace")
