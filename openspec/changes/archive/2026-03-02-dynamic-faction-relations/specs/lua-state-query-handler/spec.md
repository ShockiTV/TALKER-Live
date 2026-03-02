# lua-state-query-handler (delta)

## MODIFIED Requirements

### Requirement: Resource registry

The batch handler SHALL maintain a static resource registry mapping resource names to resolver functions. Adding a new resource SHALL require only adding an entry to this registry.

The resource registry SHALL include all memory resources (`memory.events`, `memory.summaries`, `memory.digests`, `memory.cores`, `memory.background`) alongside existing resources (`store.personalities`, `store.backstories`, `store.levels`, `store.timers`, `query.character`, `query.characters_nearby`, `query.characters_alive`, `query.world`).

Serialization of resolved data SHALL use `infra.ws.serializer` module functions instead of inline serialization.

#### Scenario: Registry includes memory resources
- **GIVEN** the resource registry
- **THEN** it SHALL contain entries for `memory.events`, `memory.summaries`, `memory.digests`, `memory.cores`, `memory.background`

#### Scenario: store.events no longer in registry
- **WHEN** resolving resource `store.events`
- **THEN** result SHALL be `{ok: false, error: "unknown resource: store.events"}`

#### Scenario: Resource registry maps store.personalities
- **WHEN** sub-query has `resource: "store.personalities"`
- **THEN** registry SHALL map it to the personalities repo character_personalities map, serialized as `{character_id, personality_id}` collection

#### Scenario: Resource registry maps query.character
- **WHEN** sub-query has `resource: "query.character"` with a `params.character_id`
- **THEN** the resolver SHALL serialize the character using `serializer.serialize_character()`

#### Scenario: Resource registry maps store.backstories
- **WHEN** sub-query has `resource: "store.backstories"`
- **THEN** registry SHALL map it to the backstories repo character_backstories map, serialized as `{character_id, backstory_id}` collection

#### Scenario: Resource registry maps store.levels
- **WHEN** sub-query has `resource: "store.levels"`
- **THEN** registry SHALL map it to the levels repo visits map, serialized as `{level_id, count, log}` collection

#### Scenario: Resource registry maps store.timers
- **WHEN** sub-query has `resource: "store.timers"`
- **THEN** registry SHALL map it to the timers repo, returning singleton `{game_time_accumulator, idle_last_check_time}`

#### Scenario: Resource registry maps query.world
- **WHEN** sub-query has `resource: "query.world"`
- **THEN** registry SHALL map it to the world context builder (location, time, weather, etc.)
- **AND** the result SHALL include `faction_standings` from `build_faction_matrix()`
- **AND** the result SHALL include `player_goodwill` from `build_player_goodwill()`

#### Scenario: query.world includes faction standings
- **WHEN** sub-query has `resource: "query.world"`
- **THEN** the result SHALL contain a `faction_standings` key with a flat dict of faction-pair relation values (e.g., `{"dolg_freedom": -1500}`)

#### Scenario: query.world includes player goodwill
- **WHEN** sub-query has `resource: "query.world"`
- **THEN** the result SHALL contain a `player_goodwill` key with a dict of per-faction goodwill values (e.g., `{"dolg": 1200}`)

#### Scenario: Unknown resource returns per-query error
- **WHEN** sub-query has an unrecognized resource name
- **THEN** the result for that sub-query SHALL have `ok: false` with a descriptive error
