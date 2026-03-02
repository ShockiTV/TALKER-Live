# faction-prompt-formatter

## Purpose

Python-side formatter that converts raw numeric faction standings and player goodwill into human-readable prompt text with threshold-based labels. Replaces the static `FACTION_RELATIONS` dict as the primary source of faction relation data for prompts.

## Requirements

### Requirement: Faction relation threshold labels

The system SHALL define threshold constants for labeling faction-pair relations based on numeric values from the engine:
- `>= 1000` → `"Allied"`
- `<= -1000` → `"Hostile"`
- Between → `"Neutral"`

#### Scenario: Allied threshold
- **WHEN** `label_faction_relation(1500)` is called
- **THEN** result SHALL be `"Allied"`

#### Scenario: Hostile threshold
- **WHEN** `label_faction_relation(-1200)` is called
- **THEN** result SHALL be `"Hostile"`

#### Scenario: Neutral threshold
- **WHEN** `label_faction_relation(500)` is called
- **THEN** result SHALL be `"Neutral"`

#### Scenario: Boundary at exactly 1000
- **WHEN** `label_faction_relation(1000)` is called
- **THEN** result SHALL be `"Allied"`

#### Scenario: Boundary at exactly -1000
- **WHEN** `label_faction_relation(-1000)` is called
- **THEN** result SHALL be `"Hostile"`

### Requirement: Player goodwill tier labels

The system SHALL define tier labels for player goodwill values matching the PDA display tiers:
- `>= 2000` → `"Excellent"`
- `>= 1500` → `"Brilliant"`
- `>= 1000` → `"Great"`
- `>= 500` → `"Good"`
- `> -500` → `"Neutral"`
- `> -1000` → `"Bad"`
- `> -1500` → `"Awful"`
- `> -2000` → `"Dreary"`
- `<= -2000` → `"Terrible"`

#### Scenario: Excellent goodwill
- **WHEN** `label_goodwill(2500)` is called
- **THEN** result SHALL be `"Excellent"`

#### Scenario: Neutral goodwill
- **WHEN** `label_goodwill(0)` is called
- **THEN** result SHALL be `"Neutral"`

#### Scenario: Terrible goodwill
- **WHEN** `label_goodwill(-2500)` is called
- **THEN** result SHALL be `"Terrible"`

### Requirement: Format faction standings text

The system SHALL provide `format_faction_standings(faction_standings, relevant_factions=None)` that converts a flat dict of faction-pair standings into formatted prompt text.

If `relevant_factions` is provided, only pairs where at least one faction is in the set SHALL be included. If None, all pairs are included.

Output format SHALL be: `"Faction A↔Faction B: Label"` (one per line), using display names from `resolve_faction_name()`.

#### Scenario: Format all standings
- **WHEN** `format_faction_standings({"dolg_freedom": -1500, "army_stalker": 0})` is called
- **THEN** result SHALL contain lines like `"Duty↔Freedom: Hostile"` and `"Army↔Loner: Neutral"`

#### Scenario: Filter to relevant factions
- **WHEN** `format_faction_standings(standings, relevant_factions={"dolg", "freedom"})` is called
- **THEN** only pairs involving dolg or freedom SHALL appear

#### Scenario: Empty standings
- **WHEN** `format_faction_standings({})` is called
- **THEN** result SHALL be an empty string

#### Scenario: None standings
- **WHEN** `format_faction_standings(None)` is called
- **THEN** result SHALL be an empty string

### Requirement: Format player goodwill text

The system SHALL provide `format_player_goodwill(player_goodwill, relevant_factions=None)` that converts a dict of faction goodwill values into formatted prompt text.

If `relevant_factions` is provided, only matching factions SHALL be included.

Output format SHALL be: `"Faction: +/-Value (Label)"` (one per line), using display names.

#### Scenario: Format goodwill
- **WHEN** `format_player_goodwill({"dolg": 1200, "freedom": -300})` is called
- **THEN** result SHALL contain `"Duty: +1200 (Great)"` and `"Freedom: -300 (Neutral)"`

#### Scenario: Filter goodwill to relevant factions
- **WHEN** `format_player_goodwill(goodwill, relevant_factions={"dolg"})` is called
- **THEN** only Duty SHALL appear

#### Scenario: Empty goodwill
- **WHEN** `format_player_goodwill({})` is called
- **THEN** result SHALL be an empty string

### Requirement: Companion faction tension note

The system SHALL provide a constant `COMPANION_FACTION_TENSION_NOTE` containing the text: "Faction hostilities apply to your attitude and dialogue, not just combat. Even if you are travelling as a companion and are mechanically safe from a hostile faction, you still hold your faction's opinions about them."

This note SHALL be injected into the system prompt by the prompt builder.

#### Scenario: Note content
- **WHEN** `COMPANION_FACTION_TENSION_NOTE` is accessed
- **THEN** it SHALL contain text about faction hostilities applying to attitude and dialogue
