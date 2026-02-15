# python-prompt-builder delta

## ADDED Requirements

### Requirement: Personality text lookup

The prompt builder SHALL resolve personality IDs to text using Python dict modules.

#### Scenario: Resolve faction personality ID
- **GIVEN** a character with `personality_id = "bandit.3"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_personality("bandit.3")` is called
- **AND** returns the personality text from texts/personality/bandit.py TEXTS["3"]

#### Scenario: Resolve unique character personality ID
- **GIVEN** a character with `personality_id = "unique.wolf"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_personality("unique.wolf")` is called
- **AND** returns the personality text from texts/personality/unique.py TEXTS["wolf"]

#### Scenario: Fallback for missing personality
- **GIVEN** a character with `personality_id = "unknown.99"`
- **WHEN** `resolve_personality("unknown.99")` is called
- **AND** no text exists in module
- **THEN** returns empty string
