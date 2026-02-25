# anomaly-data-table

## Purpose

Defines the Lua data table for anomaly section identifiers used by the anomaly trigger.

## Requirements

### Requirement: Anomaly sections data table

The system SHALL provide a pure-data Lua module at `domain/data/anomaly_sections.lua` containing a Set of all known anomaly section names and a section-to-display-name mapping. The module SHALL have zero engine dependencies and follow the established `domain/data/` pattern (like `unique_npcs.lua` and `mutant_names.lua`).

The module SHALL export:
- `is_anomaly(section)` — predicate returning `true` if the section string is a known anomaly section, `false` otherwise
- `describe(section)` — returns the human-readable display name for a known anomaly section, or `nil` if not found

All ~75 anomaly section names SHALL be sourced from `gamedata/configs/text/eng/talker_anomalies.xml` entries.

#### Scenario: Known anomaly section detected

- **WHEN** `is_anomaly("zone_mosquito_bald_average")` is called
- **THEN** it SHALL return `true`

#### Scenario: Unknown section not detected as anomaly

- **WHEN** `is_anomaly("stalker_bandit_01")` is called
- **THEN** it SHALL return `false`

#### Scenario: Nil input handled safely

- **WHEN** `is_anomaly(nil)` is called
- **THEN** it SHALL return `false` without error

#### Scenario: Display name lookup for known section

- **WHEN** `describe("zone_mosquito_bald_average")` is called
- **THEN** it SHALL return the display name string (e.g. `"Vortex"`)

#### Scenario: Display name lookup for unknown section

- **WHEN** `describe("not_a_zone")` is called
- **THEN** it SHALL return `nil`

### Requirement: Engine facade exposes anomaly predicates

The engine facade SHALL expose `is_anomaly_section(section)` and `describe_anomaly_section(section)` so that `gamedata/scripts/` trigger files can access the data table without directly requiring `bin/lua/` modules.

#### Scenario: Trigger script checks anomaly via facade

- **WHEN** a `gamedata/scripts/` file calls `talker_game_queries.is_anomaly_section("zone_buzz_weak")` (or the equivalent engine-facade path)
- **THEN** the call delegates to `anomaly_sections.is_anomaly()` and returns `true`

#### Scenario: Trigger script gets anomaly name via facade

- **WHEN** a `gamedata/scripts/` file calls the facade's describe method with `"zone_field_radioactive_average"`
- **THEN** the call delegates to `anomaly_sections.describe()` and returns the display name
