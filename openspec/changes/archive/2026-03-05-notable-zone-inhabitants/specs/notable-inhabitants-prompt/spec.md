## ADDED Requirements

### Requirement: Notable Inhabitants Prompt Section

The system SHALL provide a `build_inhabitants_context()` function in `world_context.py` that produces a "Notable Zone Inhabitants" text section listing characterized NPCs relevant to the current context.

Each entry SHALL include the character's name, role or description, faction, and alive/dead status annotation.

Format:
```
**Notable Zone Inhabitants:**
- General Voronin, leader of Duty (alive)
- Barkeep, barkeep at the 100 Rads bar in Rostok (dead)
```

#### Scenario: Inhabitants section produced with mixed alive/dead
- **WHEN** `build_inhabitants_context()` is called with alive_status showing Voronin alive and Barkeep dead
- **THEN** the output SHALL list both characters with "(alive)" and "(dead)" annotations respectively

#### Scenario: Empty inhabitants section when no characters relevant
- **WHEN** `build_inhabitants_context()` is called with no relevant characters (e.g., all notable filtered out, no leaders)
- **THEN** the function SHALL return an empty string

### Requirement: Leader characters always included

All characters with role "leader" SHALL always appear in the inhabitants section regardless of the player's current area or recent events.

#### Scenario: Leaders shown when player is in unrelated area
- **WHEN** the player is in Jupiter (l10_radar) and no leaders are area-matched
- **THEN** all leader characters (Voronin, Lukash, Sultan, etc.) SHALL still appear in the inhabitants list

#### Scenario: Dead leaders annotated in inhabitants list
- **WHEN** Voronin is dead
- **THEN** Voronin SHALL appear in the inhabitants list annotated "(dead)"
- **AND** SHALL NOT appear in a separate "dead leaders" section

### Requirement: Area-based filtering for non-leader characters

Characters with role "important" or "notable" SHALL appear in the inhabitants section only when relevant to the current context. A character is relevant when:
1. The player is in the character's associated area, OR
2. The character's story ID appears in recent events

#### Scenario: Notable character shown when player in their area
- **WHEN** Wolf has area "l01_escape" and the player is in "l01_escape"
- **THEN** Wolf SHALL appear in the inhabitants list

#### Scenario: Notable character hidden when player in different area
- **WHEN** Wolf has area "l01_escape" and the player is in "l05_bar"
- **AND** Wolf does not appear in recent events
- **THEN** Wolf SHALL NOT appear in the inhabitants list

#### Scenario: Notable character shown when referenced in recent events
- **WHEN** Wolf has area "l01_escape" and the player is in "l05_bar"
- **AND** Wolf's story ID appears in recent events
- **THEN** Wolf SHALL appear in the inhabitants list

#### Scenario: Important character without area always shown
- **WHEN** an important character has no area field set
- **THEN** that character SHALL always appear in the inhabitants list (same as leaders)

### Requirement: Character entry formatting

Each character entry SHALL be formatted as a bullet line with name, description (or role-based fallback), and status.

#### Scenario: Character with description
- **WHEN** Sidorovich has description "shady trader in the Cordon bunker"
- **THEN** his entry SHALL read: `- Sidorovich, shady trader in the Cordon bunker (alive)`

#### Scenario: Character without description uses faction fallback
- **WHEN** a character has no description field
- **THEN** the entry SHALL use the format: `- {name}, {faction_display_name} ({status})`

### Requirement: Token budget constraint

The inhabitants section SHALL stay within approximately 400 tokens. Leaders are always included (~10 entries). Non-leader characters are filtered by area/event relevance, limiting the total to roughly 15-20 entries per prompt.

#### Scenario: Filtered list stays within budget
- **WHEN** the player is in an area with 5 area-matched characters plus 10 leaders
- **THEN** the inhabitants section SHALL contain ~15 entries totaling under 400 tokens

### Requirement: Merged view replaces separate dead sections

The inhabitants section SHALL replace the existing separate "dead leaders" and "dead important characters" sections. Dead characters SHALL be annotated inline with "(dead)" rather than listed in a separate section.

#### Scenario: Dead leader appears in inhabitants not in separate section
- **WHEN** Voronin is dead
- **THEN** `build_inhabitants_context()` SHALL include "General Voronin, leader of Duty (dead)"
- **AND** the previous `build_dead_leaders_context()` output SHALL NOT be included in the aggregated world context

#### Scenario: Dead important character appears in inhabitants not in separate section
- **WHEN** Barkeep is dead and the player is in Rostok
- **THEN** `build_inhabitants_context()` SHALL include Barkeep annotated "(dead)"
- **AND** the previous `build_dead_important_context()` output SHALL NOT be included in the aggregated world context
