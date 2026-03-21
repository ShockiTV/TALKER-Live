# python-config-mirror (DELTA)

## Change

Adds support for the three new prompt compaction MCM fields.

## ADDED Requirements

### Requirement: Mirror prompt compaction fields

The `MCMConfig` model SHALL include `prompt_dialogue_pairs`, `prompt_budget_hard`, and `prompt_context_keep` fields with sensible defaults.

#### Scenario: Fields present after config sync
- **WHEN** a `config.sync` payload includes `prompt_dialogue_pairs: 3`, `prompt_budget_hard: 16`, and `prompt_context_keep: 5`
- **THEN** `config_mirror.get("prompt_dialogue_pairs")` returns `3`
- **AND** `config_mirror.get("prompt_budget_hard")` returns `16`
- **AND** `config_mirror.get("prompt_context_keep")` returns `5`

#### Scenario: Default values before sync
- **WHEN** the config mirror has not received a sync
- **THEN** `config_mirror.get("prompt_dialogue_pairs")` returns `3`
- **AND** `config_mirror.get("prompt_budget_hard")` returns `16`
- **AND** `config_mirror.get("prompt_context_keep")` returns `5`

#### Scenario: Fields in MCMConfig model
- **WHEN** `MCMConfig` is instantiated from a Lua payload
- **THEN** `prompt_dialogue_pairs` is an `int` with default `3`
- **AND** `prompt_budget_hard` is an `int` with default `16`
- **AND** `prompt_context_keep` is an `int` with default `5`

#### Scenario: Config dump includes compaction fields
- **WHEN** `config_mirror.dump()` is called
- **THEN** the returned dictionary includes `prompt_dialogue_pairs`, `prompt_budget_hard`, and `prompt_context_keep`
