# mcm-trigger-settings

## Purpose

Per-trigger MCM subsections with uniform `enable` (checkbox) + `cooldown` (input, seconds) + `chance` (input, 0–100 integer) pattern, replacing the `radio_h` On/Off/Silent system and global `base_dialogue_chance`.

## Requirements

### Requirement: Nested trigger navigation hierarchy

The MCM SHALL use nested `gr` groups to create a two-level navigation tree. The root `talker` group (no `sh`) contains `general` (`sh=true`, all non-trigger options) and `triggers` (no `sh`, navigation to per-trigger pages). Each trigger type SHALL be a `sh=true` leaf group under `triggers/` with its own options page.

#### Scenario: Death trigger has own navigation page
- **WHEN** the user navigates to TALKER Expanded → Triggers → Death
- **THEN** the options page SHALL show `enable_player`, `cooldown_player`, `chance_player`, `enable_npc`, `cooldown_npc`, `chance_npc`

#### Scenario: Injury trigger has own navigation page
- **WHEN** the user navigates to TALKER Expanded → Triggers → Injury
- **THEN** the options page SHALL show `enable`, `cooldown`, `chance`

#### Scenario: General settings on own page
- **WHEN** the user navigates to TALKER Expanded → General
- **THEN** the options page SHALL show all non-trigger settings (model, TTS, keys, config, debug, service)

#### Scenario: get() routes keys transparently
- **WHEN** `talker_mcm.get("triggers/death/enable_player")` is called
- **THEN** it SHALL resolve to `ui_mcm.get("talker/triggers/death/enable_player")`
- **AND** `talker_mcm.get("debug_logging")` SHALL resolve to `ui_mcm.get("talker/general/debug_logging")`

### Requirement: Enable checkbox replaces radio_h

Each trigger sub-type SHALL have an `enable` setting of `type = "check"` (boolean checkbox). `true` = events are created, `false` = trigger aborts entirely. This replaces the three-state `radio_h` (On/Off/Silent).

#### Scenario: Default death player enable
- **WHEN** `config.get("triggers/death/enable_player")` is called with no user override
- **THEN** it SHALL return `true`

#### Scenario: Enable false skips trigger
- **WHEN** player sets `triggers/artifact/enable_pickup` to false
- **THEN** the artifact pickup trigger SHALL not create any events

### Requirement: Chance integer input replaces base_dialogue_chance

Each trigger sub-type SHALL have a `chance` setting of `type = "input"` with `min = 0`, `max = 100`, representing percent probability. `0` = store-only (equivalent to old "Silent"), `100` = always dialogue. The global `base_dialogue_chance` (float 0.0–1.0 track) SHALL be removed.

#### Scenario: Chance 0 means store-only
- **WHEN** player sets `triggers/emission/chance` to 0
- **THEN** emission events SHALL be stored in memory but never trigger dialogue

#### Scenario: Chance 100 means always dialogue
- **WHEN** `triggers/callout/chance` is 100
- **THEN** every callout event that passes cooldown SHALL trigger dialogue

#### Scenario: Default chance values match design doc
- **WHEN** the MCM loads with defaults
- **THEN** death player/npc chance SHALL be 25
- **AND** injury chance SHALL be 25
- **AND** artifact pickup/use/equip chance SHALL be 100
- **AND** emission chance SHALL be 100
- **AND** idle chance SHALL be 100
- **AND** callout chance SHALL be 100
- **AND** taunt chance SHALL be 25
- **AND** reload chance SHALL be 10
- **AND** task chance SHALL be 10
- **AND** sleep chance SHALL be 100
- **AND** weapon_jam chance SHALL be 25
- **AND** anomaly chance SHALL be 25
- **AND** map_transition chance SHALL be 100

### Requirement: Cooldown per trigger sub-type

Each trigger sub-type that needs cooldown SHALL have a `cooldown` setting of `type = "input"` (seconds). Not all triggers need cooldown (emission, sleep, map_transition may omit it).

#### Scenario: Death cooldown defaults
- **WHEN** MCM loads with defaults
- **THEN** `triggers/death/cooldown_player` SHALL be 90
- **AND** `triggers/death/cooldown_npc` SHALL be 90

#### Scenario: Cooldown value in seconds
- **WHEN** player sets `triggers/injury/cooldown` to 60
- **THEN** the injury trigger SHALL wait 60 seconds between dialogue-triggering events

### Requirement: Config defaults entry for all new keys

The `interface/config_defaults.lua` module SHALL include default values for all new trigger MCM keys. These defaults SHALL match the values specified in the design doc's MCM structure table.

#### Scenario: All trigger keys have defaults
- **WHEN** `config_defaults` is loaded
- **THEN** it SHALL contain entries for every trigger's `enable`, `cooldown`, and `chance` keys

#### Scenario: Defaults used when MCM not loaded
- **WHEN** `config.get("triggers/death/chance_player")` is called and MCM returns nil
- **THEN** the config system SHALL fall back to the default value of 25

### Requirement: base_dialogue_chance removed

The global `base_dialogue_chance` setting SHALL be removed from the MCM and from `interface/config.lua`. Per-trigger `chance` values replace it entirely.

#### Scenario: base_dialogue_chance no longer in MCM
- **WHEN** the MCM menu is rendered
- **THEN** there SHALL be no `base_dialogue_chance` track slider

#### Scenario: config.BASE_DIALOGUE_CHANCE removed
- **WHEN** code references `config.BASE_DIALOGUE_CHANCE`
- **THEN** it SHALL not exist (or be nil)

### Requirement: Idle trigger MCM sub-modes

The idle trigger SHALL have additional sub-mode settings for emission and psy-storm contexts: `enable_during_emission`, `cooldown_during_emission`, `chance_during_emission`, `enable_during_psy_storm`, `cooldown_during_psy_storm`, `chance_during_psy_storm`.

#### Scenario: Idle during emission defaults
- **WHEN** MCM loads with defaults
- **THEN** `triggers/idle/enable_during_emission` SHALL be true
- **AND** `triggers/idle/cooldown_during_emission` SHALL be 30
- **AND** `triggers/idle/chance_during_emission` SHALL be 100

#### Scenario: Idle during psy storm defaults
- **WHEN** MCM loads with defaults
- **THEN** `triggers/idle/enable_during_psy_storm` SHALL be true
- **AND** `triggers/idle/cooldown_during_psy_storm` SHALL be 30
- **AND** `triggers/idle/chance_during_psy_storm` SHALL be 100
