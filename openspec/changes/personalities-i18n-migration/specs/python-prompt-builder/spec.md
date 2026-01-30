# python-prompt-builder delta

## ADDED Requirements

### Requirement: Personality i18n resolution

The prompt builder SHALL resolve personality IDs to localized text using python-i18n.

#### Scenario: Resolve faction personality ID
- **GIVEN** a character with `personality_id = "bandit.3"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_personality("bandit.3", locale)` is called
- **AND** returns the translated personality text from JSON

#### Scenario: Resolve unique character personality ID
- **GIVEN** a character with `personality_id = "unique.wolf"`
- **WHEN** building dialogue prompt
- **THEN** `resolve_personality("unique.wolf", locale)` is called
- **AND** returns the translated personality text from JSON

#### Scenario: Fallback for missing personality
- **GIVEN** a character with `personality_id = "unknown.99"`
- **WHEN** `resolve_personality("unknown.99", locale)` is called
- **AND** no translation exists
- **THEN** returns empty string

#### Scenario: Locale fallback to English
- **GIVEN** locale is "ru"
- **AND** personality "bandit.3" has no Russian translation
- **WHEN** `resolve_personality("bandit.3", "ru")` is called
- **THEN** falls back to English translation
