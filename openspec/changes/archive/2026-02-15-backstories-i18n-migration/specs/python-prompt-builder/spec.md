# python-prompt-builder delta

## ADDED Requirements

### Requirement: Backstory text lookup

The prompt builder SHALL resolve backstory IDs to text using Python dict modules.

#### Scenario: Resolve unique character backstory ID
- **GIVEN** a character with `backstory_id = "unique.esc_2_12_stalker_wolf"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_backstory("unique.esc_2_12_stalker_wolf")` is called
- **AND** returns the backstory text from texts/backstory/unique.py TEXTS["esc_2_12_stalker_wolf"]

#### Scenario: Resolve faction backstory ID
- **GIVEN** a character with `backstory_id = "loner.3"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_backstory("loner.3")` is called
- **AND** returns the backstory text from texts/backstory/loner.py TEXTS["3"]

#### Scenario: Fallback for missing backstory
- **GIVEN** a character with `backstory_id = "unknown.99"`
- **WHEN** `resolve_backstory("unknown.99")` is called
- **AND** no text exists in module
- **THEN** returns empty string
