## ADDED Requirements

### Requirement: Memory query resources

The resource registry SHALL support the following memory-specific resources for `state.query.batch`:

| Resource | Returns |
|----------|---------|
| `memory.events` | Array of structured event objects for a character |
| `memory.summaries` | Array of compressed memory objects for a character |
| `memory.digests` | Array of compressed memory objects for a character |
| `memory.cores` | Array of compressed memory objects for a character |
| `memory.background` | Single Background object (or null) for a character |

All memory resources require `params.character_id`.

#### Scenario: memory.events returns character events
- **WHEN** sub-query is `{"id": "ev", "resource": "memory.events", "params": {"character_id": "12467"}}`
- **THEN** result data SHALL be an array of structured event objects from character 12467's memory

#### Scenario: memory.events with from_timestamp filter
- **WHEN** sub-query includes `"params": {"character_id": "12467", "from_timestamp": 340}`
- **THEN** only events with `timestamp >= 340` SHALL be returned

#### Scenario: memory.background returns null for new character
- **WHEN** sub-query queries `memory.background` for a character with no background
- **THEN** result data SHALL be `null`

#### Scenario: memory.summaries returns compressed memories
- **WHEN** sub-query queries `memory.summaries` for a character
- **THEN** result data SHALL be an array of `{seq, tier, start_ts, end_ts, text, source_count}` objects

#### Scenario: memory resource requires character_id
- **WHEN** sub-query queries `memory.events` without `params.character_id`
- **THEN** result SHALL have `ok: false` with error about missing character_id

### Requirement: Mutation handler topic

The system SHALL register a handler for WS topic `state.mutate.batch` that dispatches mutation operations to the memory store DSL. The handler SHALL follow the same error isolation pattern as `state.query.batch`.

#### Scenario: Mutation handler registered
- **WHEN** `state.mutate.batch` message is received with `mutations` array
- **THEN** each mutation SHALL be dispatched to the memory_store DSL
- **AND** results SHALL be collected into a `state.response` message

#### Scenario: Unknown resource in mutation
- **WHEN** mutation targets an unrecognized resource
- **THEN** that mutation's result SHALL have `ok: false`
- **AND** other mutations SHALL still execute

## MODIFIED Requirements

### Requirement: Resource registry

The system SHALL support the following resources:

| Resource | Source | Returns |
|----------|--------|---------|
| `memory.events` | memory_store:query(char_id, "memory.events", params) | Array of structured event objects |
| `memory.summaries` | memory_store:query(char_id, "memory.summaries", params) | Array of CompressedMemory objects |
| `memory.digests` | memory_store:query(char_id, "memory.digests", params) | Array of CompressedMemory objects |
| `memory.cores` | memory_store:query(char_id, "memory.cores", params) | Array of CompressedMemory objects |
| `memory.background` | memory_store:query(char_id, "memory.background", params) | Single Background object or null |
| `store.personalities` | personalities repo (character_personalities map) | Array of {character_id, personality_id} objects |
| `store.backstories` | backstories repo (character_backstories map) | Array of {character_id, backstory_id} objects |
| `store.levels` | levels repo (visits map) | Array of {level_id, count, log[]} objects |
| `store.timers` | timers repo | Single object {game_time_accumulator, idle_last_check_time} |
| `query.character` | game_adapter.get_character_by_id(id) | Single Character object |
| `query.characters_nearby` | game_adapter.get_characters_near(center, radius) | Array of Character objects |
| `query.characters_alive` | alife() story object checks | Object mapping story_id to boolean |
| `query.world` | talker_game_queries (location, time, weather, etc.) | Single SceneContext object |

#### Scenario: store.events is removed from registry
- **WHEN** sub-query has `resource: "store.events"`
- **THEN** result SHALL have `ok: false` with error `"unknown resource: store.events"`

#### Scenario: store.memories is removed from registry
- **WHEN** sub-query has `resource: "store.memories"`
- **THEN** result SHALL have `ok: false` with error `"unknown resource: store.memories"`

#### Scenario: memory.events returns structured events
- **WHEN** sub-query is `{"id": "ev", "resource": "memory.events", "params": {"character_id": "12467"}}`
- **THEN** result data SHALL be an array of `{seq, timestamp, type, context}` objects

#### Scenario: query.character returns character data
- **WHEN** sub-query is `{"id": "c", "resource": "query.character", "params": {"id": "123"}}`
- **THEN** result data SHALL contain serialized Character fields (game_id, name, faction, etc.)

#### Scenario: query.world returns scene context
- **WHEN** sub-query is `{"id": "w", "resource": "query.world"}`
- **THEN** result data SHALL contain loc, poi, time, weather, emission, psy_storm, sheltering, campfire, brain_scorcher_disabled, miracle_machine_disabled

## REMOVED Requirements

### Requirement: Resource registry (store.events and store.memories entries)
**Reason**: `store.events` (global event store) is replaced by per-NPC `memory.events`. `store.memories` (flat narrative) is replaced by `memory.*` tier resources.
**Migration**: Use `memory.events` with `character_id` param instead of `store.events`. Use `memory.summaries`/`memory.digests`/`memory.cores`/`memory.background` instead of `store.memories`.
