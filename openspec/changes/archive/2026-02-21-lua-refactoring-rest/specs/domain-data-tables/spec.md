## ADDED Requirements

### Requirement: Unique NPC data module

The system SHALL provide `domain/data/unique_npcs.lua` containing a set of story IDs for all unique/important NPCs. The module SHALL have zero engine dependencies.

#### Scenario: Module loads without engine
- **WHEN** `require("domain.data.unique_npcs")` is called outside the STALKER engine
- **THEN** it returns a table with an `is_unique(story_id)` function and/or a set table

#### Scenario: Known unique NPC returns true
- **WHEN** `unique_npcs.is_unique("esc_m_trader")` is called
- **THEN** it returns `true`

#### Scenario: Unknown NPC returns false
- **WHEN** `unique_npcs.is_unique("random_stalker_123")` is called
- **THEN** it returns `false` (or `nil`)

#### Scenario: Data matches original important_npcs
- **WHEN** the set is compared with the `important_npcs` table in `talker_game_queries.script`
- **THEN** they contain the same set of story IDs

### Requirement: Mutant names data module

The system SHALL provide `domain/data/mutant_names.lua` containing a pattern-to-name mapping table for mutant identification, plus a `describe(technical_name)` function.

#### Scenario: Module loads without engine
- **WHEN** `require("domain.data.mutant_names")` is called outside the STALKER engine
- **THEN** it returns a table with the mutant name mappings

#### Scenario: Known mutant pattern matches
- **WHEN** `mutant_names.describe("m_bloodsucker_e_01")` is called
- **THEN** it returns `"a Bloodsucker"`

#### Scenario: Unknown mutant returns technical name
- **WHEN** `mutant_names.describe("mod_custom_creature")` is called
- **THEN** it returns `"a mod_custom_creature"`

#### Scenario: Dog pattern checked last to avoid pseudodog collision
- **WHEN** `mutant_names.describe("m_pseudodog_01")` is called
- **THEN** it returns `"a Pseudodog"` (not `"a Dog"`)

### Requirement: Ranks data module

The system SHALL provide `domain/data/ranks.lua` containing rank name-to-value mappings and reputation tier thresholds.

#### Scenario: Rank value lookup
- **WHEN** `ranks.get_value("veteran")` is called
- **THEN** it returns `4`

#### Scenario: Unknown rank returns -1
- **WHEN** `ranks.get_value("unknown_rank")` is called
- **THEN** it returns `-1`

#### Scenario: Reputation tier for positive value
- **WHEN** `ranks.get_reputation_tier(1500)` is called
- **THEN** it returns `"Brilliant"`

#### Scenario: Reputation tier for negative value
- **WHEN** `ranks.get_reputation_tier(-1200)` is called
- **THEN** it returns `"Awful"`

#### Scenario: Reputation tier for nil
- **WHEN** `ranks.get_reputation_tier(nil)` is called
- **THEN** it returns `"Neutral"`

#### Scenario: Reputation tier for non-number
- **WHEN** `ranks.get_reputation_tier("not_a_number")` is called
- **THEN** it returns `"unknown"` without crashing

### Requirement: Character event info formatting

The system SHALL provide a function (in `domain/data/` or extended in `domain/model/character.lua`) to format character information for event descriptions.

#### Scenario: Monster character info
- **WHEN** character has `faction = "Monster"` and `name = "Bloodsucker"`
- **THEN** formatted info is `"Bloodsucker (Monster)"`

#### Scenario: Human character info without disguise
- **WHEN** character has `name = "Wolf"`, `experience = "veteran"`, `faction = "Loner"`, `reputation = "Good"`
- **THEN** formatted info is `"Wolf (veteran Loner, Good rep)"`

#### Scenario: Human character info with disguise
- **WHEN** character has `name = "Spy"`, `faction = "Freedom"`, `visual_faction = "Duty"`
- **THEN** formatted info includes `"[disguised as Duty]"`

#### Scenario: Nil character
- **WHEN** character is nil
- **THEN** formatted info is `"Unknown"`
