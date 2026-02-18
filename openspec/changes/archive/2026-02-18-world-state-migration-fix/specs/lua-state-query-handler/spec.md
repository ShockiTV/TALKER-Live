# lua-state-query-handler (delta)

## ADDED Requirements

### Requirement: Characters Alive Query Handler

The system SHALL handle `state.query {type: "characters.alive", ids: [...]}` requests.

#### Scenario: Query characters alive status
- **WHEN** Python sends characters.alive query with ids=["id1", "id2"]
- **THEN** handler iterates over IDs
- **AND** for each ID, finds server object via `get_story_object(id)`
- **AND** checks alive status with fallback logic (see below)
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

### Requirement: Info Portions in Scene Query

The system SHALL include info portion status in the world.context query response.

#### Scenario: Brain Scorcher status included
- **WHEN** Python sends world.context query
- **THEN** response includes brain_scorcher_disabled boolean
- **AND** value is true if has_alife_info("sar_ozerki_switcher_on")
- **AND** value is false otherwise

#### Scenario: Miracle Machine status included
- **WHEN** Python sends world.context query
- **THEN** response includes miracle_machine_disabled boolean
- **AND** value is true if has_alife_info("sar2_monolith_peace")
- **AND** value is false otherwise

## MODIFIED Requirements

### Requirement: World Context Query Handler

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
- `brain_scorcher_disabled`: Boolean
- `miracle_machine_disabled`: Boolean

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

