## ADDED Requirements

### Requirement: Lean Character DTO
The `Character` entity in both Lua and Python must not contain `backstory` or `personality` fields.

#### Scenario: Lua Character Creation
- **WHEN** a new `Character` object is created in Lua via `game_adapter.lua`
- **THEN** it does not fetch or attach `backstory` or `personality` data.

#### Scenario: Python Character Deserialization
- **WHEN** Python receives a `game.event` payload containing `witnesses`
- **THEN** the deserialized `Character` objects do not contain `backstory` or `personality` fields.

### Requirement: Lazy Generation of Traits in Lua
Lua must handle the generation and persistence of missing narrative traits when queried by Python.

#### Scenario: Querying a Missing Personality
- **WHEN** Python sends a `BatchQuery` for `store.personalities` for a character ID that has no assigned personality
- **THEN** Lua's query handler generates a new personality, saves it to the store, and returns the new personality ID.

#### Scenario: Querying a Missing Backstory
- **WHEN** Python sends a `BatchQuery` for `store.backstories` for a character ID that has no assigned backstory
- **THEN** Lua's query handler generates a new backstory, saves it to the store, and returns the new backstory ID.

### Requirement: Two-Phase Fetch in Python
Python's `DialogueGenerator` must fetch traits on-demand in two distinct phases to optimize data transfer.

#### Scenario: Phase 1 - Speaker Selection
- **WHEN** an event triggers dialogue generation
- **THEN** `DialogueGenerator` first executes a `BatchQuery` to fetch `store.personalities` for all valid witnesses.
- **AND** passes these personalities as a dictionary to the speaker selection prompt.

#### Scenario: Phase 2 - Dialogue Generation
- **WHEN** a speaker has been selected
- **THEN** `DialogueGenerator` executes a second `BatchQuery` to fetch `store.backstories` (and memory) specifically for the chosen speaker.
- **AND** passes the backstory and personality to the dialogue generation prompt.
