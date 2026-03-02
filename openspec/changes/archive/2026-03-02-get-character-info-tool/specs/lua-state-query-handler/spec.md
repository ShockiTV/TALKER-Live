## ADDED Requirements

### Requirement: query.character_info resource handler

The state query handler SHALL register a `query.character_info` resource in the resource registry. The handler SHALL accept `params.id` (character ID string), resolve the character via `game_adapter.get_character_by_id()`, derive gender from `sound_prefix`, resolve squad members, include backgrounds from memory store, and trigger squad discovery side-effects for new squad members.

#### Scenario: Resolve character with squad and backgrounds
- **WHEN** `query.character_info` is called with `params.id = "12467"` for a character in a 3-member squad
- **THEN** the handler SHALL return `{character: {..., gender, background}, squad_members: [{...}, {...}]}`
- **AND** the main character SHALL be excluded from `squad_members`

#### Scenario: Character not found returns error
- **WHEN** `query.character_info` is called with a non-existent character ID
- **THEN** the handler SHALL raise an error `"Character not found: <id>"`

#### Scenario: Character with no squad returns empty array
- **WHEN** the character is not part of any squad
- **THEN** `squad_members` SHALL be `[]`

#### Scenario: Squad discovery creates memory entries
- **WHEN** a squad member has no entry in `memory_store`
- **THEN** the handler SHALL create a memory entry for that squad member
- **AND** SHALL backfill global events from `global_event_buffer`

#### Scenario: Handler dispatched via state.query.batch
- **WHEN** a `state.query.batch` request contains a sub-query with `resource: "query.character_info"`
- **THEN** the batch dispatcher SHALL route it to the registered `query.character_info` handler
