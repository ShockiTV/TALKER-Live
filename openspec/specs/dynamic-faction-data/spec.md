# dynamic-faction-data

## Purpose

Lua-side builders that extract live faction×faction relation values and player goodwill from the game engine, returning structured numeric data for inclusion in the `query.world` response payload.

## Requirements

### Requirement: Build faction matrix

The system SHALL provide a `build_faction_matrix()` function in `talker_game_queries.script` that iterates all gameplay factions and returns a flat dict of faction-pair relation values.

The factions list SHALL include: `stalker`, `dolg`, `freedom`, `csky`, `ecolog`, `killer`, `army`, `bandit`, `monolith`, `renegade`, `greh`, `isg`.

Keys SHALL use the format `"<faction_a>_<faction_b>"` (underscore-delimited, sorted alphabetically within each pair to avoid duplicates like both `dolg_freedom` and `freedom_dolg`).

Values SHALL be raw integers from `relation_registry.community_relation(faction_a, faction_b)`.

Only unique pairs SHALL be included (no self-pairs, no reverse duplicates).

#### Scenario: Matrix contains all unique pairs
- **WHEN** `build_faction_matrix()` is called
- **THEN** return value SHALL be a table with keys like `"dolg_freedom"`, `"army_stalker"`, etc.
- **AND** each value SHALL be a raw integer from `relation_registry.community_relation()`

#### Scenario: Pair keys are alphabetically sorted
- **WHEN** building the matrix for Duty and Freedom
- **THEN** the key SHALL be `"dolg_freedom"` (not `"freedom_dolg"`)

#### Scenario: Self-pairs excluded
- **WHEN** iterating factions
- **THEN** no key like `"dolg_dolg"` SHALL appear in the result

#### Scenario: relation_registry unavailable
- **WHEN** `relation_registry` global is nil
- **THEN** `build_faction_matrix()` SHALL return an empty table `{}`

### Requirement: Build player goodwill

The system SHALL provide a `build_player_goodwill()` function in `talker_game_queries.script` that returns a dict of per-faction player goodwill values.

Keys SHALL be faction technical IDs. Values SHALL be raw integers from `actor:community_goodwill(faction)`.

#### Scenario: Goodwill returned for all factions
- **WHEN** `build_player_goodwill()` is called
- **THEN** result SHALL contain entries for each gameplay faction
- **AND** each value SHALL be a raw integer

#### Scenario: Actor not available
- **WHEN** `db.actor` is nil (e.g., loading screen)
- **THEN** `build_player_goodwill()` SHALL return an empty table `{}`

#### Scenario: Goodwill values reflect runtime state
- **WHEN** player has +1200 goodwill with Duty
- **THEN** result SHALL contain `dolg = 1200`

### Requirement: Faction list constant

The system SHALL define a module-level constant `GAMEPLAY_FACTIONS` listing the technical IDs of all factions that participate in the relation matrix.

#### Scenario: Faction list includes core factions
- **WHEN** `GAMEPLAY_FACTIONS` is referenced
- **THEN** it SHALL contain at minimum: `stalker`, `dolg`, `freedom`, `csky`, `ecolog`, `killer`, `army`, `bandit`, `monolith`

#### Scenario: Faction list includes alternate factions
- **WHEN** `GAMEPLAY_FACTIONS` is referenced
- **THEN** it SHALL also contain: `renegade`, `greh`, `isg`
