# python-config-mirror (DELTA)

## Change

Adds support for the two new prompt compaction MCM fields.

## ADDED Requirements

### Requirement: Mirror prompt compaction fields

The `MCMConfig` model SHALL include `prompt_dialogue_pairs` and `prompt_budget_hard` fields with sensible defaults.

#### Scenario: Fields present after config sync
- **WHEN** a `config.sync` payload includes `prompt_dialogue_pairs: 3` and `prompt_budget_hard: 16`
- **THEN** `config_mirror.get("prompt_dialogue_pairs")` returns `3`
- **AND** `config_mirror.get("prompt_budget_hard")` returns `16`

#### Scenario: Default values before sync
- **WHEN** the config mirror has not received a sync
- **THEN** `config_mirror.get("prompt_dialogue_pairs")` returns `3`
- **AND** `config_mirror.get("prompt_budget_hard")` returns `16`

#### Scenario: Fields in MCMConfig model
- **WHEN** `MCMConfig` is instantiated from a Lua payload
- **THEN** `prompt_dialogue_pairs` is an `int` with default `3`
- **AND** `prompt_budget_hard` is an `int` with default `16`

#### Scenario: Config dump includes compaction fields
- **WHEN** `config_mirror.dump()` is called
- **THEN** the returned dictionary includes `prompt_dialogue_pairs` and `prompt_budget_hard`
