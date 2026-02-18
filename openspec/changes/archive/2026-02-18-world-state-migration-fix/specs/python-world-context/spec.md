# python-world-context

## Purpose

World state context builder for dialogue prompts. Provides important character registry, alive/dead status queries, and prompt section generation for world state context.

## ADDED Requirements

### Requirement: Important Characters Registry

The system SHALL maintain a registry of important characters with static metadata.

Characters are categorized by role:
- **Leader**: Faction leaders (Voronin, Lukash, Sultan, etc.)
- **Important**: Major story characters (Sidorovich, Barkeep, Sakharov, etc.)
- **Notable**: Recurring characters with area associations

Each character entry SHALL include:
- `story_id`: Game's unique identifier (e.g., "bar_visitors_barman_stalker_trader")
- `name`: Display name
- `role`: "leader" | "important" | "notable"
- `faction`: Faction ID (e.g., "dolg", "freedom", "stalker")
- `area`: Optional location ID where character operates (e.g., "l01_escape")
- `description`: Brief description of character

#### Scenario: Registry contains faction leaders
- **WHEN** the registry is loaded
- **THEN** it contains entries for Voronin (Duty), Lukash (Freedom), Sultan (Bandits), Dushman (Mercs), Chernobog (Sin)

#### Scenario: Registry contains important characters
- **WHEN** the registry is loaded
- **THEN** it contains entries for Sidorovich, Barkeep, Beard, Professor Sakharov, Forester

#### Scenario: Notable characters have area associations
- **WHEN** registry contains notable character "Wolf"
- **THEN** his entry includes area="l01_escape"

### Requirement: Query Characters Alive Status

The system SHALL query Lua for alive/dead status of specified characters.

#### Scenario: Query single character alive
- **WHEN** query_characters_alive(["bar_visitors_barman_stalker_trader"]) is called
- **THEN** Python sends ZMQ query `state.query {type: "characters.alive", ids: ["bar_visitors_barman_stalker_trader"]}`
- **AND** returns dict mapping story_id to boolean

#### Scenario: Multiple characters queried
- **WHEN** query_characters_alive(["id1", "id2", "id3"]) is called
- **THEN** single ZMQ query sent with all IDs
- **AND** returns {"id1": true, "id2": false, "id3": true}

#### Scenario: Unknown character returns false
- **WHEN** query includes story_id for non-existent character
- **THEN** that character maps to false in response

### Requirement: Build Dead Leaders Context

The system SHALL generate prompt text for dead faction leaders.

#### Scenario: One dead faction leader
- **GIVEN** Voronin (Duty leader) is dead
- **WHEN** build_dead_leaders_context is called
- **THEN** returns text: "General Voronin, leader of Duty, is dead."

#### Scenario: Multiple dead leaders
- **GIVEN** Voronin and Lukash are dead
- **WHEN** build_dead_leaders_context is called
- **THEN** returns text listing both deaths

#### Scenario: No dead leaders
- **GIVEN** all faction leaders are alive
- **WHEN** build_dead_leaders_context is called
- **THEN** returns empty string

### Requirement: Build Dead Important Characters Context

The system SHALL generate prompt text for dead important characters (non-leaders).

#### Scenario: Important character died
- **GIVEN** Sidorovich is dead
- **WHEN** build_dead_important_context is called
- **THEN** returns text mentioning Sidorovich's death with description

#### Scenario: Notable filtered by area
- **GIVEN** Wolf (area=l01_escape) is dead
- **AND** player is NOT in l01_escape
- **WHEN** build_dead_important_context is called
- **THEN** Wolf is NOT included in output

#### Scenario: Notable shown when player in area
- **GIVEN** Wolf (area=l01_escape) is dead
- **AND** player IS in l01_escape
- **WHEN** build_dead_important_context(current_area="l01_escape") is called
- **THEN** Wolf IS included in output

### Requirement: Build Info Portions Context

The system SHALL generate prompt text for major world events from info portions.

#### Scenario: Brain Scorcher disabled
- **GIVEN** scene data has brain_scorcher_disabled=true
- **WHEN** build_info_portions_context is called
- **THEN** returns text: "The Brain Scorcher in Radar has been disabled again, opening the path to the North."

#### Scenario: Miracle Machine disabled
- **GIVEN** scene data has miracle_machine_disabled=true
- **WHEN** build_info_portions_context is called
- **THEN** returns text: "The Miracle Machine in Yantar has been disabled again."

#### Scenario: Neither disabled
- **GIVEN** both info portions are false
- **WHEN** build_info_portions_context is called
- **THEN** returns empty string

### Requirement: Build Regional Politics Context

The system SHALL generate context-specific political information.

#### Scenario: Cordon truce shown when in Cordon
- **GIVEN** player is in l01_escape (Cordon)
- **WHEN** build_regional_context(current_area="l01_escape") is called
- **THEN** returns text about temporary Army-Loner truce at Cordon

#### Scenario: No regional context for other areas
- **GIVEN** player is in l05_bar (Rostok)
- **WHEN** build_regional_context(current_area="l05_bar") is called
- **THEN** returns empty string

### Requirement: Aggregate World Context for Prompts

The system SHALL provide `build_world_context(scene_data, recent_events)` that aggregates all context sections.

#### Scenario: Full world context built
- **WHEN** build_world_context is called with scene_data
- **THEN** result includes dead leaders section if any
- **AND** includes dead important characters section if any
- **AND** includes info portions section if any disabled
- **AND** includes regional politics section if applicable

#### Scenario: Empty world context when nothing notable
- **GIVEN** all leaders alive, no info portions, no regional context
- **WHEN** build_world_context is called
- **THEN** returns empty string or minimal context

