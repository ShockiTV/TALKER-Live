# world-description-builder

## Purpose

Pure string assembly for world context descriptions, extracted from `talker_game_queries.script` into `bin/lua/interface/world_description.lua`. All environment data is passed as parameters — no engine calls inside the module.

## Requirements

### Requirement: World description builder exists at interface/world_description.lua

The system SHALL provide `interface/world_description.lua` containing pure string assembly functions for world descriptions. The module SHALL have zero engine dependencies — all environment data SHALL be passed as parameters.

#### Scenario: Module loads without engine
- **WHEN** `require("interface.world_description")` is called outside the STALKER engine
- **THEN** the module loads successfully

### Requirement: build_description assembles world context string

The module SHALL provide `build_description(params)` that assembles a formatted world description string from pre-resolved environment data.

#### Scenario: Full world description
- **WHEN** `build_description({ location = "Rostok", time_of_day = "morning", weather = "partially cloudy", shelter = "", campfire = "lit" })` is called
- **THEN** it returns `"In Rostok at morning during partially cloudy weather, next to a lit campfire."`

#### Scenario: Description without campfire
- **WHEN** `build_description({ location = "Cordon", time_of_day = "night", weather = "rain", shelter = "", campfire = nil })` is called
- **THEN** it returns `"In Cordon at night during rain weather."`

#### Scenario: Description with shelter
- **WHEN** `build_description({ location = "Army Warehouses", time_of_day = "evening", weather = "rain", shelter = "and sheltering inside", campfire = nil })` is called
- **THEN** the shelter text is included between time and weather

#### Scenario: Unlit campfire included
- **WHEN** campfire param is `"unlit"`
- **THEN** description includes `", next to an unlit campfire"`

#### Scenario: Location dots replaced with commas
- **WHEN** location contains periods (e.g., `"Rostok. 100 Rads Bar"`)
- **THEN** periods are replaced with commas in the output

### Requirement: time_of_day converts hour to description

The module SHALL provide `time_of_day(hour)` that maps an integer hour (0-23) to a time-of-day string.

#### Scenario: Night hours (0-5)
- **WHEN** `time_of_day(3)` is called
- **THEN** it returns `"night"`

#### Scenario: Morning hours (6-9)
- **WHEN** `time_of_day(8)` is called
- **THEN** it returns `"morning"`

#### Scenario: Noon hours (10-14)
- **WHEN** `time_of_day(12)` is called
- **THEN** it returns `"noon"`

#### Scenario: Evening hours (15-19)
- **WHEN** `time_of_day(17)` is called
- **THEN** it returns `"evening"`

#### Scenario: Late night hours (20-23)
- **WHEN** `time_of_day(22)` is called
- **THEN** it returns `"night"`

### Requirement: describe_emission resolves emission state

The module SHALL provide `describe_emission(is_psy_storm, is_surge)` that returns an emission description string from boolean flags.

#### Scenario: Psy storm ongoing
- **WHEN** `describe_emission(true, false)` is called
- **THEN** it returns `"ongoing psy storm"`

#### Scenario: Surge ongoing
- **WHEN** `describe_emission(false, true)` is called
- **THEN** it returns `"ongoing emission"`

#### Scenario: No emission
- **WHEN** `describe_emission(false, false)` is called
- **THEN** it returns `""`

### Requirement: describe_weather resolves weather string

The module SHALL provide `describe_weather(weather_string, emission_string)` that normalizes weather descriptions and overrides with emission if present.

#### Scenario: Normal weather
- **WHEN** `describe_weather("clear", "")` is called
- **THEN** it returns `"clear"`

#### Scenario: Partly translated
- **WHEN** `describe_weather("partly", "")` is called
- **THEN** it returns `"partially cloudy"`

#### Scenario: Weather overridden by emission
- **WHEN** `describe_weather("clear", "ongoing emission")` is called
- **THEN** it returns `"an ongoing emission"`

### Requirement: describe_shelter resolves shelter status

The module SHALL provide `describe_shelter(rain_factor, rain_exposure)` that determines shelter description from weather parameters.

#### Scenario: Sheltered from rain
- **WHEN** `describe_shelter(0.5, 0.05)` is called (rain > 0.2, exposure < 0.1)
- **THEN** it returns `"and sheltering inside"`

#### Scenario: Not sheltered
- **WHEN** `describe_shelter(0.1, 0.5)` is called
- **THEN** it returns `""`

#### Scenario: No rain
- **WHEN** `describe_shelter(0.0, 0.0)` is called
- **THEN** it returns `""`
