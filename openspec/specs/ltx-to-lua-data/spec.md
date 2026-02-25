# ltx-to-lua-data

## Purpose

Defines the migration of backstory and personality data from LTX config files to pure Lua data tables.

## Requirements

### Requirement: Backstory data as Lua table

The system SHALL provide `domain/repo/backstory_data.lua` containing all backstory ID mappings as a pure Lua table, replacing `ini_file("talker\\backstories.ltx")` reads.

#### Scenario: Data module loads without engine
- **WHEN** `require("domain.repo.backstory_data")` is called outside the game engine
- **THEN** it returns a table with faction keys mapping to arrays of IDs

#### Scenario: Data contains all factions
- **WHEN** the module is loaded
- **THEN** it contains entries for: `unique`, `generic`, `army`, `bandit`, `clearsky`, `duty`, `ecolog`, `freedom`, `isg`, `mercenary`, `monolith`, `renegade`, `sin`

#### Scenario: Unique IDs are strings
- **WHEN** the `unique` entry is accessed
- **THEN** it contains an array of string IDs (e.g., `"esc_m_trader"`, `"esc_2_12_stalker_wolf"`)

#### Scenario: Faction IDs are numbers
- **WHEN** a faction entry like `generic` is accessed
- **THEN** it contains an array of numeric IDs (e.g., `{1, 2, 3, ...}`)

### Requirement: Personality data as Lua table

The system SHALL provide `domain/repo/personality_data.lua` containing all personality ID mappings as a pure Lua table, replacing `ini_file("talker\\personalities.ltx")` reads.

#### Scenario: Data module loads without engine
- **WHEN** `require("domain.repo.personality_data")` is called outside the game engine
- **THEN** it returns a table with faction keys mapping to arrays of IDs

#### Scenario: Data contains all factions
- **WHEN** the module is loaded
- **THEN** it contains entries for: `generic`, `bandit`, `ecolog`, `monolith`, `renegade`, `sin`, `zombied`

### Requirement: Backstories module uses Lua data tables

`domain/repo/backstories.lua` SHALL use `require("domain.repo.backstory_data")` instead of `ini_file()`. The module SHALL NOT reference the `ini_file` global.

#### Scenario: Backstory lookup without engine
- **WHEN** `backstories.get_backstory(character)` is called in tests
- **THEN** it returns a valid backstory ID from the data table without calling `ini_file()`

#### Scenario: Backstory for unique character
- **WHEN** character with tech_name `"esc_m_trader"` requests a backstory
- **AND** that name exists in `backstory_data.unique`
- **THEN** the backstory ID is `"unique.esc_m_trader"`

#### Scenario: Backstory for faction character
- **WHEN** a character with faction `"bandit"` requests a backstory
- **THEN** a random ID from `backstory_data.bandit` is selected and returned as `"bandit.<id>"`

### Requirement: Personalities module uses Lua data tables

`domain/repo/personalities.lua` SHALL use `require("domain.repo.personality_data")` instead of `ini_file()`. The module SHALL NOT reference the `ini_file` global.

#### Scenario: Personality lookup without engine
- **WHEN** `personalities.get_personality(character)` is called in tests
- **THEN** it returns a valid personality ID from the data table without calling `ini_file()`

#### Scenario: Personality for faction character
- **WHEN** a character with faction `"monolith"` requests a personality
- **THEN** a random ID from `personality_data.monolith` is selected and returned as `"monolith.<id>"`

### Requirement: Data tables match .ltx file contents exactly

The generated Lua data tables SHALL contain exactly the same IDs as the corresponding .ltx files (no additions, no removals).

#### Scenario: Backstory data matches backstories.ltx
- **WHEN** `backstory_data.generic` is compared with `[generic] ids = ...` from `backstories.ltx`
- **THEN** both contain the same set of IDs

#### Scenario: Personality data matches personalities.ltx
- **WHEN** `personality_data.bandit` is compared with `[bandit] ids = ...` from `personalities.ltx`
- **THEN** both contain the same set of IDs
