# talker-mcm (DELTA)

## Change

Adds two MCM input fields for prompt compaction settings.

## ADDED Requirements

### Requirement: MCM prompt_dialogue_pairs field

The MCM SHALL include a numeric input field `prompt_dialogue_pairs` in the General Configuration section. The value is a plain integer representing how many recent dialogue turn pairs to keep. Default: `3`. Min: `0`. Max: `20`.

#### Scenario: Default dialogue pairs
- **WHEN** the player has not changed the `prompt_dialogue_pairs` setting
- **THEN** the MCM returns `3`

#### Scenario: Player sets zero for maximum pruning
- **WHEN** the player sets `prompt_dialogue_pairs` to `0`
- **THEN** `config.get_all_config()` includes `prompt_dialogue_pairs: 0`

#### Scenario: Player raises for more conversational history
- **WHEN** the player sets `prompt_dialogue_pairs` to `8`
- **THEN** `config.get_all_config()` includes `prompt_dialogue_pairs: 8`

### Requirement: MCM prompt_budget_hard field

The MCM SHALL include a numeric input field `prompt_budget_hard` in the General Configuration section. The value represents thousands of tokens (e.g., `16` means 16000 tokens). Default: `16`. Min: `4`. Max: `128`.

#### Scenario: Default hard budget
- **WHEN** the player has not changed the `prompt_budget_hard` setting
- **THEN** the MCM returns `16`

#### Scenario: Player raises hard budget for large context models
- **WHEN** the player sets `prompt_budget_hard` to `32`
- **THEN** `config.get_all_config()` includes `prompt_budget_hard: 32`

#### Scenario: Player lowers hard budget for small context models
- **WHEN** the player sets `prompt_budget_hard` to `6`
- **THEN** `config.get_all_config()` includes `prompt_budget_hard: 6`

### Requirement: Compaction fields in config_defaults

The `config_defaults` module SHALL include both `prompt_dialogue_pairs` (default `3`) and `prompt_budget_hard` (default `16`).

#### Scenario: Defaults available without engine
- **WHEN** `require("interface.config_defaults")` is called
- **THEN** the returned table contains `prompt_dialogue_pairs = 3` and `prompt_budget_hard = 16`
