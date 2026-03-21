# get-character-info-tool

## Purpose

LLM tool that returns detailed character information including gender, background, and squad members with discovery side-effects. Covers the tool schema, Lua query resource handler, Python tool handler, serialization format, and squad discovery memory entry creation.

## Requirements

### Requirement: get_character_info tool schema

The system SHALL provide a `get_character_info` tool definition with a single required parameter `character_id` (string). The tool SHALL return an object with `character` (object with id, name, faction, rank, gender, background) and `squad_members` (array of objects with the same shape).

#### Scenario: Tool schema registered in ConversationManager
- **WHEN** ConversationManager is initialized
- **THEN** the TOOLS list SHALL include `get_character_info` alongside `get_memories` and `background`
- **AND** the tool description SHALL explain it returns character info with squad members

#### Scenario: Tool requires character_id parameter
- **WHEN** the LLM calls `get_character_info` without `character_id`
- **THEN** the tool call SHALL fail with a validation error

### Requirement: Python tool handler

The system SHALL provide a `_handle_get_character_info(character_id)` method on ConversationManager that sends a `state.query.batch` with a `query.character_info` sub-query and returns the formatted result.

#### Scenario: Handler dispatches query to Lua
- **WHEN** the LLM calls `get_character_info(character_id="12467")`
- **THEN** the handler SHALL send `state.query.batch` with `resource: "query.character_info"` and `params: {"id": "12467"}`
- **AND** SHALL return the Lua response as-is (character + squad_members)

#### Scenario: Handler returns empty squad for character with no squad
- **WHEN** Lua returns a character with empty `squad_members`
- **THEN** the handler SHALL return `{"character": {...}, "squad_members": []}`

#### Scenario: Handler formats result for LLM
- **WHEN** the tool result is returned to the LLM
- **THEN** it SHALL be formatted as a readable text summary including character name, faction, gender, background traits (if present), and each squad member's info

#### Scenario: Handler handles query failure
- **WHEN** the state query for `query.character_info` fails
- **THEN** the handler SHALL return `{"error": "..."}` with a descriptive message
- **AND** SHALL log a warning

### Requirement: Lua query.character_info resource handler

The system SHALL register a `query.character_info` resource in the state query handler resource registry. The handler SHALL accept `params.id` (character ID), resolve the character object, derive gender, resolve squad members, include backgrounds from memory store, and apply squad discovery side-effects.

#### Scenario: Character resolved by ID
- **WHEN** `query.character_info` receives `params.id = "12467"`
- **THEN** the handler SHALL call `game_adapter.get_character_by_id("12467")`
- **AND** SHALL return the character with all standard fields plus `gender` and `background`

#### Scenario: Character not found
- **WHEN** the character ID does not exist in the game
- **THEN** the handler SHALL raise an error `"Character not found: <id>"`

#### Scenario: Squad members resolved
- **WHEN** the character belongs to a squad with 3 members (including self)
- **THEN** `squad_members` SHALL contain 2 entries (excluding the character itself)
- **AND** each squad member SHALL have the same field shape as `character` (id, name, faction, gender, background)

#### Scenario: Character has no squad
- **WHEN** the character is not part of any squad
- **THEN** `squad_members` SHALL be an empty array `[]`

### Requirement: Gender derivation from sound_prefix

The `query.character_info` handler SHALL derive a `gender` field for each character (main character and squad members) from their `sound_prefix` attribute. This field SHALL NOT be added to the Character domain model — it is derived at serialization time only.

#### Scenario: Female character identified by sound_prefix
- **WHEN** a character has `sound_prefix == "woman"`
- **THEN** `gender` SHALL be `"female"` in the response

#### Scenario: Male character identified by sound_prefix
- **WHEN** a character has `sound_prefix` other than `"woman"` (e.g., `"stalker_1"`, `"bandit_2"`)
- **THEN** `gender` SHALL be `"male"` in the response

#### Scenario: Gender included for all characters in response
- **WHEN** `query.character_info` returns a character with 2 squad members
- **THEN** `gender` SHALL be present on the main `character` object AND on each `squad_members` entry

### Requirement: Background inclusion in response

The `query.character_info` handler SHALL read each character's background from `memory_store` and include it in the response. If no background exists, the field SHALL be `null`.

#### Scenario: Character has existing background
- **WHEN** character "12467" has a background in memory store with traits, backstory, and connections
- **THEN** `character.background` SHALL contain the full background object

#### Scenario: Character has no background
- **WHEN** character "55891" has no background in memory store
- **THEN** `character.background` SHALL be `null` (Lua `nil` → JSON `null`)

#### Scenario: Squad members include backgrounds
- **WHEN** squad member A has a background and squad member B does not
- **THEN** squad member A's entry SHALL have `background: {...}` and squad member B's entry SHALL have `background: null`

### Requirement: Squad discovery side-effect

When `query.character_info` is processed, the handler SHALL check each squad member against `memory_store`. For squad members without an existing memory entry, the handler SHALL create a new entry and backfill from `global_event_buffer`. This is one of two memory entry creation paths (the other being the witness/fan-out path).

#### Scenario: New squad member gets memory entry
- **WHEN** `query.character_info` resolves squad member "55891" who has no memory entry
- **THEN** the handler SHALL create a memory entry for "55891" in `memory_store`
- **AND** SHALL backfill global events from `global_event_buffer` into the new entry

#### Scenario: Existing squad member unchanged
- **WHEN** `query.character_info` resolves squad member "12467" who already has a memory entry
- **THEN** no new entry SHALL be created (idempotent)
- **AND** the existing background SHALL be included in the response

#### Scenario: Squad discovery is idempotent
- **WHEN** `query.character_info` is called twice for the same character
- **THEN** squad members SHALL NOT get duplicate memory entries or duplicate global events

### Requirement: Serialization format

The `infra/ws/serializer.lua` module SHALL provide a `serialize_character_info(char, squad_members, memory_store)` function that builds the extended response format with gender and background for each character.

#### Scenario: Full response serialized
- **WHEN** a character with 2 squad members is serialized
- **THEN** the result SHALL be `{character: {game_id, name, faction, ..., gender, background}, squad_members: [{game_id, name, ..., gender, background}, ...]}`

#### Scenario: Gender derived during serialization
- **WHEN** `serialize_character_info` processes a character with `sound_prefix = "woman"`
- **THEN** the `gender` field SHALL be `"female"` in the serialized output

#### Scenario: Background read from memory store
- **WHEN** `serialize_character_info` looks up background for a character
- **THEN** it SHALL query `memory_store` for that character's background
- **AND** SHALL include the result (or nil) in the serialized output

### Requirement: System prompt updated with tool instructions

The ConversationManager system prompt SHALL include instructions for the `get_character_info` tool alongside existing `get_memories` and `background` tool instructions.

#### Scenario: System prompt describes get_character_info
- **WHEN** ConversationManager builds the system prompt
- **THEN** it SHALL include a description of `get_character_info(character_id)` explaining it returns character info, gender, background, and squad members

#### Scenario: System prompt explains when to use get_character_info
- **WHEN** the system prompt lists tool usage instructions
- **THEN** it SHALL advise the LLM to call `get_character_info` when it needs squad composition or when generating a background for a character it hasn't spoken as before
